import json
import logging
import random
import re

# Create your views here.
from django import http
from django.views import View
from django_redis import get_redis_connection

from utils import constants
from utils.response_code import RET
from verifications.libs.captcha.captcha import captcha

logger = logging.getLogger('django')


class ImageCodeView(View):
    '''
    需求：获取图片验证码
    '''

    def get(self, request):
        # 接收参数
        cur_uuid = request.GET.get('cur')
        pre_uuid = request.GET.get('pre')

        # 校验参数
        if not cur_uuid:
            return http.HttpResponseForbidden('参数不全')
        # 检验参数格式
        if not re.match(r'^\w{8}(-\w{4}){3}-\w{12}', cur_uuid):
            return http.HttpResponseForbidden('参数格式不正确')
        if pre_uuid and not re.match(r'^\w{8}(-\w{4}){3}-\w{12}', pre_uuid):
            return http.HttpResponseForbidden('参数格式不正确')
        # 生成验证码
        text, image = captcha.generate_captcha()
        logger.info('图形验证码是：%s' % text)
        # 将验证码保存到redis数据库中
        redis_conn = get_redis_connection('verify_code')
        try:
            # 删除之前的
            redis_conn.delete('ImageCode_' + pre_uuid)
            # 保存当前的
            redis_conn.setex('ImageCode_' + cur_uuid, constants.IMAGE_CODE_REDIS_EXPIRES, text)
        except Exception as e:
            logger.error(e)
            return http.HttpResponseServerError('生成图形验证码失败')
        else:
            return http.HttpResponse(image, content_type='image/jpg')


class SMSCodeView(View):
    '''手机验证码'''

    def post(self, request):
        # 1.接收参数
        dict_data = json.loads(request.body.decode())
        mobile = dict_data.get('mobile')
        image_code_id = dict_data.get('id')
        image_code = dict_data.get('text')
        # 2.创建redis实例对象
        redis_conn = get_redis_connection('verify_code')
        # 判断手机号的标记是否存在
        sms_code_flag = redis_conn.get('sms_code_flag_%s' % mobile)
        if sms_code_flag:
            return http.JsonResponse({'errno': RET.REQERR, 'errmsg': '请求过于频繁'})
        # 3.校验参数
        if not all([mobile, image_code, image_code_id]):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数错误'})
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数错误'})
        try:
            real_image_code = redis_conn.get('ImageCode_' + image_code_id)
            if not real_image_code:
                return http.JsonResponse({'errno': RET.NODATA, 'errmsg': '验证码已过期'})
            redis_conn.delete('ImageCode_' + image_code_id)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': '数据库查询错误'})
        # 因为redis数据库读出来的数据是bytes类型，所以要decode
        if image_code.upper() != real_image_code.decode().upper():
            return http.JsonResponse({'errno': RET.DATAERR, 'errmsg': '验证码输入错误'})
        # 3.生成手机号验证码
        sms_code = '%06d' % random.randint(0, 999999)
        logger.info('短信验证码为：%s' % sms_code)
        # 4.将手机验证码保存到redis
        pl = redis_conn.pipeline()
        pl.setex('sms_%s' % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
        pl.setex('sms_code_flag_%s' % mobile, constants.SEND_SMS_CODE_INTERVAL, 1)
        pl.execute()
        # 5.发送短信
        # try:
        #     result = CCP().send_sms_code(mobile, [sms_code, constants.SMS_CODE_REDIS_EXPIRES // 60], 1)

        return http.JsonResponse({'errno': RET.OK, 'errmsg': '发送短信成功'})
