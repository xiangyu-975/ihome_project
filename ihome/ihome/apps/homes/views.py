import json
import logging

from django import http
from django.conf import settings
from django.db import transaction
from django.shortcuts import render

# Create your views here.
from django.utils.decorators import method_decorator
from django.views import View
from pymysql import DatabaseError

from homes.models import Area, House, Facility, HouseImage
from libs.qiniuyun.qiniu_storage import storage
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
