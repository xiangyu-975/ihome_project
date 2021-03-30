import json
import re

from django import http
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render
from utils.response_code import RET
# Create your views here.
from django.views import View


class RegisterView(View):

    def post(self, request):
        # 一.接收参数，根据文档接收
        dict_data = json.loads(request.body.decode())
        mobile = dict_data.get('mobile')
        phonecode = dict_data.get('phonecode')
        password = dict_data.get('password')
        # 二.校验参数
        # 校验传入参数是否齐全
        if not all([mobile, phonecode, password]):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数不全'})
        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '请输入8-20位密码'})
        # 判断手机号是否合法
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '请输入正确的手机号'})

        return http.JsonResponse({'errno': RET.OK, 'errmsg': '注册成功'})


class LoginView(View):
    '''登陆实现'''

    def get(self, request):
        # 1.判断用户是否登陆,需要获取user
        user = request.user
        # 2.对user进行认证
        if not user.is_authenticated:
            return http.JsonResponse({'errno': RET.SESSIONERR, 'errmsg': '用户未登陆'})
        data = {
            'user_id': user.id,
            'username': user.username
        }
        return http.JsonResponse({'errno': RET.OK, 'errmsg': '已登陆', 'data': data})

    def post(self, request):
        dict_data = json.loads(request.body.decode())
        mobile = dict_data.get('mobile')
        password = dict_data.get('password')
        # 校验参数
        # 判断参数是否齐全
        if not all([mobile, password]):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数不全'})
        # 判断密码是否为8~20位
        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '请输入正确的密码'})
        # 判断手机号是否合法
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '请输入正确的手机号'})
        # 认证用户鞥路
        user = authenticate(username=mobile, password=password)
        if user is None:
            return http.JsonResponse({'errno': RET.LOGINERR, 'errmsg': '请输入正确的手机号'})
        # 实现状态保持
        login(request, user)
        return http.JsonResponse({'errno': RET.OK, 'errmsg': '登陆成功'})

    def delete(self, request):
        # 退出登陆
        logout(request)
        return http.JsonResponse({'errno': RET.OK, 'errmsg': '退出成功'})
