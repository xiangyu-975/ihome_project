import logging
import re

# Create your views here.
from django import http
from django.views import View
from django_redis import get_redis_connection

from utils import constants
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
