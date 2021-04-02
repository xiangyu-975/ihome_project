import logging

from qiniu import Auth, put_data, etag
import qiniu.config

# 需要填写自己的Access_key和secret_key
access_key = '66IMdEOiu0A0nLerMIaynq1Up71Re7GNmcWf_Hkj'
secret_key = 'qKT40T7syV3nKVYa5DTqeMkr6QJkhpRn4b2svZEj'
# 要上传的空间
bucket_name = 'xyaijia'


def storage(data):
    '''封装七牛云上传文件接口'''
    if not data:
        return None
    try:
        # 构建鉴权对象
        q = Auth(access_key, secret_key)

        # 上传后保存的文件名
        key = None
        # 生成上传 Token，可以指定过期时间等
        token = q.upload_token(bucket_name)
        # 要上传文件的本地路径
        # localfile = './sync/bbb.jpg'
        ret, info = put_data(token, key, data)
    except Exception as e:
        logging.error(e)
        raise e
    if info and info.status_code != 200:
        raise Exception('上传文件到七牛云失败')

    # 返回七牛保存的图片名，这个图片名也是访问七牛云获取图片的路径
    print(info)
    print(ret['key'])
    return ret['key']
    # assert ret['key'] == key
    # assert ret['hash'] == etag(localfile)


if __name__ == '__main__':
    file_name = input('请输入要上传的文件')
    with open(file_name, "rb") as f:
        storage(f.read())
