import math

from django.core.validators import MinValueValidator
from django.db import models
from django.contrib.auth.models import User
from django.utils.safestring import mark_safe
from django.utils.text import Truncator
from markdown import markdown
from django.db.models.signals import post_save
from django.dispatch import receiver


# model for simpatik
# ----------------------------------------------------------------------------------------
class Location(models.Model):
    location = models.CharField(max_length=255, blank=False)

    def __str__(self):
        return self.location


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_location = models.ForeignKey(Location, related_name='profile', on_delete=models.PROTECT)

    def __str__(self):
        return str(self.user_location)

    @receiver(post_save, sender=User)
    def create_or_update_user_profile(sender, instance, created, **kwargs):
        if created:
            default_user_loc = Location.objects.get(pk=1)
            Profile.objects.create(user=instance, user_location=default_user_loc)
        instance.profile.save()
    # @receiver(post_save, sender=User)
    # def create_user_profile(sender, instance, created, **kwargs):
    #     if created:
    #         Profile.objects.create(user=instance)
    #
    # @receiver(post_save, sender=User)
    # def save_user_profile(sender, instance, **kwargs):
    #     instance.profile.save()


class Item(models.Model):
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=1000)
    picture = models.ImageField(upload_to='items', blank=True)
    quantity = models.IntegerField()
    booked_quantity = models.IntegerField(default=0)
    item_location = models.ForeignKey(Location, related_name='items', on_delete=models.PROTECT)
    item_created_dt = models.DateTimeField(auto_now_add=True)
    item_created_by = models.ForeignKey(User, related_name='items', on_delete=models.DO_NOTHING)
    item_updated_dt = models.DateTimeField(null=True)
    item_updated_by = models.ForeignKey(User, null=True, related_name='+', on_delete=models.DO_NOTHING)

    def __str__(self):
        return self.name

class Cart(models.Model):
    cart_item = models.ForeignKey(Item, related_name='carts', on_delete=models.DO_NOTHING)
    item_qty = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1, message="Tidak boleh kurang dari 1")])
    cart_user = models.ForeignKey(User, related_name='carts', on_delete=models.DO_NOTHING)
    
    def __str__(self):
        return str(self.cart_item)

class TransactionStatus(models.Model):
    status = models.CharField(max_length=25, null=False)

    def __str__(self):
        return str(self.status)

DEFAULT_STATUS_ID = 1
class Transaction(models.Model):
    transaction_no = models.CharField(max_length=30)
    transaction_sts = models.ForeignKey(TransactionStatus, default=DEFAULT_STATUS_ID, related_name='transactions', on_delete=models.PROTECT)
    tr_created_dt = models.DateTimeField(auto_now_add=True)
    tr_created_by = models.ForeignKey(User, related_name='transactions', on_delete=models.DO_NOTHING)
    tr_updated_dt = models.DateTimeField(null=True)
    tr_updated_by = models.ForeignKey(User, null=True, related_name='+', on_delete=models.DO_NOTHING)

    def __str__(self):
        return self.transaction_no

class TransactionDetail(models.Model):
    transaction_no = models.ForeignKey(Transaction, related_name='details', on_delete=models.PROTECT)
    seq_no = models.PositiveIntegerField(default=0, null=False)
    item = models.ForeignKey(Item, related_name='details', on_delete=models.DO_NOTHING)
    detail_qty = models.PositiveIntegerField(default=0)

    def __str__(self):
        return str(self.transaction_no)+str(self.seq_no)

    # def save(self, *args, **kwargs):
    #     if self.pk:
    #         self.seq_no += 1
    #     # Write all your logic here, like handeling max value etc
    #
    #     return super(TransactionDetail, self).save(*args, **kwargs)


# ----------------------------------------------------------------------------------------
class Board(models.Model):
    name = models.CharField(max_length=30, unique=True)
    description = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    def get_posts_count(self):
        return Post.objects.filter(topic__board=self).count()

    def get_last_post(self):
        return Post.objects.filter(topic__board=self).order_by('-created_at').first()


class Topic(models.Model):
    subject = models.CharField(max_length=255)
    last_updated = models.DateTimeField(auto_now_add=True)
    board = models.ForeignKey(Board, related_name='topics', on_delete=models.CASCADE)
    starter = models.ForeignKey(User, related_name='topics', on_delete=models.CASCADE)
    views = models.PositiveIntegerField(default=0)  # <- here

    def __str__(self):
        return self.subject

    def get_page_count(self):
        count = self.posts.count()
        pages = count / 2
        return math.ceil(pages)

    def has_many_pages(self, count=None):
        if count is None:
            count = self.get_page_count()
        return count > 6

    def get_page_range(self):
        count = self.get_page_count()
        if self.has_many_pages(count):
            return range(1, 5)
        return range(1, count + 1)

    def get_last_ten_posts(self):
        return self.posts.order_by('-created_at')[:10]


class Post(models.Model):
    message = models.TextField(max_length=4000)
    topic = models.ForeignKey(Topic, related_name='posts', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)
    created_by = models.ForeignKey(User, related_name='posts', on_delete=models.CASCADE)
    updated_by = models.ForeignKey(User, null=True, related_name='+', on_delete=models.SET_NULL)

    def __str__(self):
        truncated_message = Truncator(self.message)
        return truncated_message.chars(30)

    def get_message_as_markdown(self):
        return mark_safe(markdown(self.message, safe_mode='escape'))
