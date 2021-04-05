import datetime
import json
import logging

from django import http
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import render
from django.core.paginator import Paginator
# Create your views here.
from django.utils.decorators import method_decorator
from django.views import View
from django_redis import get_redis_connection
from pymysql import DatabaseError

from homes.models import Area, House, Facility, HouseImage
from libs.qiniuyun.qiniu_storage import storage
from utils import constants
from utils.decorators import login_required
from utils.param_checking import image_file
from utils.response_code import RET

logger = logging.getLogger('django')


class AreaView(View):
    '''查询地址'''

    def get(self, request):
        try:
            data = Area.objects.all()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': '数据库查询失败'})
        areas_list = [area.to_dict() for area in data]

        return http.JsonResponse({'errno': RET.OK, 'errmsg': '获取成功', 'data': areas_list})


class HouseView(View):
    def get(self, request):
        # 获取所有参数
        agrs = request.GET
        area_id = agrs.get('aid', '')
        start_date_str = agrs.get('sd', '')
        end_date_str = agrs.get('ed', '')
        # booking(订单量), price-inc(低到高), price-des(高到低),
        sort_key = agrs.get('sk', 'new')
        page = agrs.get('p', '1')
        try:
            page = int(page)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数错误'})
        redis_conn = get_redis_connection('house_cache')
        try:
            redis_key = 'houses_%s_%s_%s_%s' % (area_id, start_date_str, end_date_str, sort_key)
            data = redis_conn.hget(redis_key, page)
            if data:
                return http.JsonResponse({'errno': RET.OK, 'errmsg': 'OK', 'data': json.loads(data)})
        except Exception as e:
            logger.error(e)
        # 对日期进行相关处理
        try:
            start_date = None
            end_date = None
            if start_date_str:
                start_date = datetime.datetime.strftime(start_date_str, '%Y-%m-%d')
            if end_date_str:
                end_date = datetime.datetime.strftime(end_date_str, '%Y-%m-%d')
            # 如果开始时间大于或者等于结束时间，就报错
            if start_date and end_date:
                assert start_date > end_date, Exception('开始时间大于结束时间')
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数错误'})
        filters = {}
        # 如果区域ID存在
        if area_id:
            filters['area_id'] = area_id
        # 定义数组保存冲突的订单
        if start_date and end_date:
            # 如果订单的开始时间 < 结束时间 and 订单结束时间 > 开始时间
            conflict_order = Order.objects.filter(begin_date__lt=end_date, end_date__gt=start_date)
        elif start_date:
            # 订单结束时间大于开始时间
            conflict_order = Order.objects.filter(end_date__gt=start_date)
        elif end_date:
            # 订单开始时间小于结束时间
            conflict_order = Order.objects.filter(start_date__lt=end_date)
        else:
            conflict_order = []
        # 取到冲突订单的房屋ID
        conflict_house_id = [order.house_id for order in conflict_order]
        # 添加条件：查询到的房屋不包括冲突订单的中的房屋ID
        if conflict_house_id:
            filters['id__in'] = conflict_house_id
        # 查询数据
        if sort_key == 'booking':
            # 订单量从高到底
            houses_query = House.objects.filter(**filters).order_by('-order_count')
            # 价格从低到高
        elif sort_key == 'price-inc':
            houses_query = House.objects.filter(**filters).order_by('price')
            # 价格从高到低
        elif sort_key == 'price-des':
            houses_query = House.objects.filter(**filters).order_by('-price')
            # 默认创建时间最新
        else:
            houses_query = House.objects.filter(**filters).order_by('-create_time')
        paginator = Paginator(houses_query, constants.HOUSE_LIST_PAGE_CAPACITY)
        # 获取当前对象
        page_houses = paginator.page(page)
        # 获取总页数
        total_page = paginator.num_pages
        houses = [house.to_basic_dict() for house in page_houses]
        data = {
            'total_page': total_page,
            'houses': houses,
        }
        if page <= total_page:
            try:
                # 生成缓存用的key
                redis_key = 'houses_%s_%s_%s_%s' % (area_id, start_date_str, end_date_str, sort_key)
                # 获取 redis_store 的 pipeline 对象，其可以一次做多个redis操作
                pl = redis_conn.pipeline()
                # 开启事务
                pl.multi()
                # 缓存数据
                pl.hset(redis_key, page, json.dumps(data))
                # 设置有效期时间
                pl.expire(redis_key, constants.HOUSE_LIST_REDIS_EXPIRES)
                # 提交事务
                pl.execute()
            except Exception as e:
                logger.error(e)
        return http.JsonResponse({'errno': RET.OK, 'errmsg': 'OK', 'data': data})

    # 发布房源
    @method_decorator(login_required)
    def post(self, request):
        # 获取用户
        user = request.user
        # 获取数据
        dict_data = json.loads(request.body.decode())
        title = dict_data.get('title')
        price = dict_data.get('price')
        area_id = dict_data.get('area_id')
        address = dict_data.get('address')
        room_count = dict_data.get('room_count')
        acreage = dict_data.get('acreage')
        unit = dict_data.get('unit')
        capacity = dict_data.get('capacity')
        beds = dict_data.get('beds')
        deposit = dict_data.get('deposit')
        min_days = dict_data.get('min_days')
        max_days = dict_data.get('max_days')

        if not all(
                [title, price, area_id, address, room_count, acreage, unit, capacity, beds, deposit, min_days,
                 max_days]):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数错误'})
        try:
            price = int(float(price) * 100)
            deposit = int(float(deposit) * 100)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.NODATA, 'errmsg': '参数错误'})
        try:
            area = Area.objects.get(id=area_id)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.NODATA, 'errmsg': '地址不存在'})
        with transaction.atomic():
            save_id = transaction.savepoint()
            # 设置数据到模型中
            house = House()
            house.user = user
            house.area = area
            house.title = title
            house.price = price
            house.address = address
            house.room_count = room_count
            house.acreage = acreage
            house.unit = unit
            house.capacity = capacity
            house.beds = beds
            house.deposit = deposit
            house.min_days = min_days
            house.max_days = max_days
            try:
                house.save()
            except Exception as e:
                logger.error(e)
                transaction.savepoint_rollback(save_id)
                return http.JsonResponse({'errno': RET.DBERR, 'errmsg': '数据库保存失败'})
            try:
                # 设置设施信息
                facility_ids = dict_data.get('facility')
                if facility_ids:
                    facilities = Facility.objects.filter(id__in=facility_ids)
                    for facility in facilities:
                        house.facility.add(facility)
            except DatabaseError as e:
                logger.error(e)
                transaction.savepoint_rollback(save_id)
                return http.JsonResponse({'errno': RET.DBERR, 'errmsg': '保存数据失败'})
            transaction.savepoint_commit(save_id)
        return http.JsonResponse({'errno': RET.OK, 'errmsg': '发布成功', 'data': {'house_id': house.pk}})


class UserHouseView(View):
    '''显示用户房源信息'''

    @method_decorator(login_required)
    def get(self, request):
        user = request.user
        houses = [house.to_basic_dict() for house in user.houses.all()]
        return http.JsonResponse({'errno': RET.OK, 'errmsg': '成功', 'data': {'houses': houses}})


class HouseImageView(View):
    '''
    房源图片上传
    '''

    def post(self, request, house_id):
        house_image = request.FILES.get('house_image')
        if not house_image:
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数错误'})
        if not image_file(house_image):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数错误'})
        try:
            house = House.objects.get(id=house_id)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.NODATA, 'errmsg': '房间不存在'})
        # 读取文件的二进制数据
        house_image_data = house_image.read()
        try:
            key = storage(house_image_data)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.THIRDERR, 'errmsg': '图片上传失败'})
        with transaction.atomic():
            save_id = transaction.savepoint()
            try:
                if not house.index_image_url:
                    house.index_image_url = key
                    house.save()
                house_image = HouseImage()
                house_image.house = house
                house_image.url = key
                house_image.save()
            except Exception as e:
                logger.error(e)
                transaction.savepoint_rollback(save_id)
            transaction.savepoint_commit(save_id)

        data = {
            'url': settings.QINIU_URL + key
        }
        return http.JsonResponse({'errno': RET.OK, 'errmsg': 'OK', 'data': data})


class HouseIndexView(View):
    '''首页推荐房间显示'''

    def get(self, request):
        houses_list = cache.get('house_index')
        if not houses_list:
            try:
                houses = House.objects.order_by('-order_count')[0:5]
            except Exception as e:
                logger.error(e)
                return http.JsonResponse({'errno': RET.DBERR, 'errmsg': '查询数据库失败'})
            houses_list = [house.to_basic_dict() for house in houses]
            cache.set('house_index', houses_list, 3600)

        # 返回数据
        return http.JsonResponse({'errno': RET.OK, 'errmsg': 'OK', 'data': houses_list})


class HouseDetailView(View):
    '''显示房间详情'''

    def get(self, request, house_id):
        try:
            house = House.objects.get(id=house_id)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数错误'})
        user = request.user
        if not user.is_authenticated:
            user_id = -1
        else:
            user_id = user.id
        # 先从redis中取
        redis_conn = get_redis_connection('house_cache')
        house_dict = redis_conn.get('house_info_' + house_id)
        # 如果有值，那么返回数据
        if house_dict:
            return http.JsonResponse(
                {'errno': RET.OK, 'errmsg': 'OK', 'data': {"user_id": user_id, 'house': json.loads(house_dict)}})
        # 将数据缓存到redis中
        house_dict = house.to_full_dict()
        try:
            redis_conn.setex('house_info_' + house_id, constants.HOUSE_DETAIL_REDIS_EXPIRE_SECOND,
                             json.dumps(house_dict))
        except Exception as e:
            logger.error(e)
        # 返回数据
        return http.JsonResponse({'errno': RET.OK, 'errmsg': 'OK', 'data': {'user_id': user_id, 'house': house_dict}})
