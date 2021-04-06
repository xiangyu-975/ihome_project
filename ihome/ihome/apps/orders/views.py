import datetime
import json
import logging

from django import http
from django.shortcuts import render

# Create your views here.
from django.utils.decorators import method_decorator
from django.views import View

from homes.models import House
from orders.models import Order
from utils.decorators import login_required
from utils.response_code import RET

logger = logging.getLogger('django')


class OrderView(View):
    '''订单'''

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(OrderView, self).dispatch(*args, **kwargs)

    def get(self, request):
        user = request.user
        role = request.GET.get('role')
        if not role:
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数错误'})
        if role not in ['landlord', 'custom']:
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数错误'})
        if role == 'custom':
            # 查询当前自己下了哪些订单
            orders = Order.objects.filter(user=user).order_by('-create_time')
        else:
            # 查询自己的房源都有哪些订单
            houses = House.objects.filter(user=user)
            house_ids = [house.id for house in houses]
            orders = Order.objects.filter(house_id__in=house_ids).order_by('-create_time')
        orders_dict = [order.to_dict() for order in orders]
        print(orders_dict)
        return http.JsonResponse({'errno': RET.OK, 'errmsg': '发布成功', 'data': {'orders': orders_dict}})

    def post(self, request):
        # 获取当前用户
        user = request.user
        # 获取传入的参数
        dict_data = json.loads(request.body.decode())
        house_id = dict_data.get('house_id')
        start_date_str = dict_data.get('start_date')
        end_date_str = dict_data.get('end_date')
        # 校验参数
        if not all([house_id, start_date_str, end_date_str]):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数错误'})
        try:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d')
            assert start_date < end_date, Exception('开始日期大于结束日期')
            # 计算入住时间
            days = (end_date - start_date).days
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数错误'})
        # 判断房屋是否存在
        try:
            house = House.objects.get(id=house_id)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '房屋不存在'})
        # 判断房屋是否是用户登陆的
        if user.id == house.user.id:
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '不能订购自己的房源'})
        # 查询是否存在冲突的订单
        try:
            filters = {'house': house, 'begin_date__lt': end_date, 'end_date__gt': start_date}
            count = Order.objects.filter(**filters).count()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '数据库查询错误'})
        if count > 0:
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '房间已经被预定'})
        amount = days * house.price
        # 生成订单模型
        order = Order()
        order.user = user
        order.house = house
        order.begin_date = start_date
        order.end_date = end_date
        order.days = days
        order.house_price = house.price
        order.amount = amount
        try:
            order.save()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': '数据库保存失败'})
        return http.JsonResponse({'errno': RET.OK, 'errmsg': '下单成功', 'data': {'order_id': order.pk}})


class OrdersStatusView(View):
    '''接单和拒单'''

    @method_decorator(login_required)
    def put(self, request, order_id):
        user = request.user
        data_dict = json.loads(request.body.decode())
        action = data_dict.get('action')
        if action not in ['action', 'reason']:
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数错误'})
        try:
            order = Order.objects.filter(id=order_id, status=Order.ORDER_STATUS['WAIT_ACCEPT']).first()
            house = order.house
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': '查询数据失败'})
        # 判断订单是否存在并且当前房屋是用户id还是当前用户id
        if not order or house.user != user:
            return http.JsonResponse({'errno': RET.NODATA, 'errmsg': '数据有误'})
        if action == 'accept':
            # 接单
            order.status = Order.ORDER_STATUS['WAIT_COMMENT']
        elif action == 'reject':
            # 获取拒单原因
            reason = data_dict.get('reason')
            if not reason:
                return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '未填写拒绝原因'})

            # 设置状态为拒单并设置拒绝理由
            order.status = Order.ORDER_STATUS['REJECTED']
            order.comment = reason
        # 保存在数据库
        try:
            order.save()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': '保存订单失败'})
        return http.JsonResponse({'errno': RET.OK, 'errmsg': 'OK'})
