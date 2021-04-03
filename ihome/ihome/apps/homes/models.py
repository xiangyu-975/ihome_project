from django.conf import settings
from django.db import models

# Create your models here.
from utils.model import BaseModel


class Area(BaseModel):
    '''城区类'''
    name = models.CharField(max_length=32, null=False, verbose_name='区域名字')

    class Meta:
        db_table = 'tb_area'

    def to_dict(self):
        """将对象转换为字典数据"""
        area_dict = {
            'aid': self.pk,
            'aname': self.name
        }
        return area_dict


class Facility(BaseModel):
    '''设施信息'''
    name = models.CharField(max_length=32, null=False, verbose_name='设施名字')

    class Meta:
        db_table = 'tb_facility'


class House(BaseModel):
    user = models.ForeignKey('users.User', related_name='houses', on_delete=models.CASCADE, verbose_name='房屋主人的用户编号')
    area = models.ForeignKey('Area', null=False, on_delete=models.CASCADE, verbose_name='归属地的地区编号')
    title = models.CharField(max_length=64, null=False, verbose_name='标题')
    price = models.IntegerField(default=0)  # 单价 单位：分
    address = models.CharField(max_length=512, default='')  # 地址
    room_count = models.IntegerField(default=1)  # 房间数目
    acreage = models.IntegerField(default=0)  # 房屋面积
    unit = models.CharField(max_length=32, default='')  # 房屋单元 ，如几室几厅
    capacity = models.IntegerField(default=1)  # 可以容纳几人
    beds = models.CharField(max_length=64, default='')  # 房屋床铺的配置
    deposit = models.IntegerField(default=0)  # 房屋押金
    min_days = models.IntegerField(default=1)  # 最少入住天数
    max_days = models.IntegerField(default=0)  # 最大入住 0 表示不限制
    order_count = models.IntegerField(default=0)  # 预定房间的订单数
    index_image_url = models.CharField(max_length=256, default='')  # 房屋主图片的路径
    facility = models.ManyToManyField('Facility', verbose_name='和设施表之间多对多的关系')

    class Meta:
        db_table = 'tb_house'

    def to_basic_dict(self):
        house_dict = {
            'house_id': self.pk,
            'order_count': self.order_count,
            'title': self.title,
            'ctime': self.create_time,
            'price': self.price,
            'area_name': self.area.name,
            'address': self.address,
            'room_count': self.room_count,
            'img_url': settings.QINIU_URL + self.index_image_url if self.index_image_url else '',
            'user_avatar': settings.QINIU_URL + self.user.avatar.name if self.user.avatar.name else '',
        }
        return house_dict


class HouseImage(BaseModel):
    '''
    房屋图片列表
    '''
    house = models.ForeignKey('House', on_delete=models.CASCADE)  # 房屋编号
    url = models.CharField(max_length=256, null=False)  # 图片路径

    class Meta:
        db_table = 'tb_house_image'
