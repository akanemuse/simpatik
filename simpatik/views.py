from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import transaction
from django.db.models import Count, F, Q
from django.forms import ModelForm
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import UpdateView, ListView

from .forms import NewTopicForm, PostForm, AddNewItemForm, AddNewItemCartForm
from .models import Board, Post, Topic, Item, Cart, Transaction, TransactionDetail, TransactionStatus
from django.contrib import messages
import datetime
import http.client, urllib
from decouple import config


# Create your views here.
# start simpatik main app views
# User view
@login_required()
def home(request):
    diajukan = TransactionStatus.objects.get(status='diajukan')
    transactions = Transaction.objects.filter(tr_created_by__profile__user_location=request.user.profile.user_location, transaction_sts=diajukan)\
        .order_by('tr_created_dt')[:3]
    my_requests = Transaction.objects.filter(tr_created_by=request.user, transaction_sts=diajukan).order_by('tr_created_dt')[:3]
    return render(request, 'simpatik/home.html', {'transactions': transactions, 'my_requests': my_requests})

@method_decorator(login_required, name='dispatch')
class PermintaanItem(ListView):
    model = Item
    context_object_name = 'items'
    template_name = 'simpatik/permintaan.html'
    paginate_by = 9

    # def get_context_data(self, **kwargs):
    #     kwargs['board'] = self.board
    #     return super().get_context_data(**kwargs)

    def get_queryset(self):
        queryset = Item.objects.filter(item_location=self.request.user.profile.user_location).order_by('-item_updated_dt')\
            .annotate(tersedia=F('quantity')-F('booked_quantity'))
        return queryset

@login_required()
def book(request, pk):
    item = get_object_or_404(Item, pk=pk)
    try:
        cart = Cart.objects.get(Q(cart_item=item), Q(cart_user=request.user))
        if request.method == 'POST':
            form = AddNewItemCartForm(request.POST, instance=cart)
            if form.is_valid():
                cart.save()
                messages.success(request, 'Barang berhasil diubah')
                return redirect('permintaan')
            else:
                messages.warning(request, 'Error, silakan perbaiki error berikut')
        else:
            form = AddNewItemCartForm(request.POST or None, instance=cart)
    except Cart.DoesNotExist:
        if request.method == 'POST':
            form = AddNewItemCartForm(request.POST)
            if form.is_valid():
                cart = form.save(commit=False)
                cart.cart_item = item
                cart.cart_user = request.user
                cart.save()
                messages.success(request, 'Barang berhasil ditambahkan')
                return redirect('permintaan')
            else:
                messages.warning(request, 'Error, silakan perbaiki error berikut')
        else:
            form = AddNewItemCartForm()
    return render(request, 'simpatik/cart.html', {'form': form, 'item': item})

@method_decorator(login_required, name='dispatch')
class PermintaaanDetail(ListView):
    model = Cart
    context_object_name = 'carts'
    template_name = 'simpatik/permintaan_detail.html'
    paginate_by = 10

    # def get_context_data(self, **kwargs):
    #     kwargs['board'] = self.board
    #     return super().get_context_data(**kwargs)

    def get_queryset(self):
        queryset = Cart.objects.filter(cart_user=self.request.user).order_by('cart_item')
        return queryset

@login_required()
def delete_cart_item(request, pk):
    try:
        cart_item = Cart.objects.filter(pk=pk, cart_user=request.user)
        cart_item.delete()
        messages.success(request, 'Berhasil hapus barang')
    except Exception as e:
        messages.error(request, 'Hapus barang gagal')

    return redirect('permintaan_detail')

@login_required()
def submit_request(request):
    try:
        carts = Cart.objects.filter(cart_user=request.user)
        last_tr = Transaction.objects.all().order_by('-transaction_no').first()
        diajukan = TransactionStatus.objects.get(status='diajukan')
        if last_tr != None:
            last_tr_dt = last_tr.transaction_no[0:8]
            last_tr_no = last_tr.transaction_no[8:11]
            current_dt = datetime.datetime.today().strftime('%Y%m%d')
            if current_dt == last_tr_dt:
                transaction_no = current_dt+str(int(last_tr_no)+1).zfill(3)
            else:
                transaction_no = current_dt+'001'
        else:
            transaction_no = datetime.datetime.today().strftime('%Y%m%d') + '001'

        try:
            with transaction.atomic():
                #transaction header
                tr_header = Transaction(transaction_no=transaction_no, tr_created_by=request.user, transaction_sts=diajukan)
                tr_header.save()

                #transaction detail
                for count, item in enumerate(carts, start=1):
                    #get cart and save it to detail transaction
                    tr_dtl = TransactionDetail(transaction_no=tr_header,
                                               seq_no=count,
                                               item=item.cart_item,
                                               detail_qty=item.item_qty)
                    tr_dtl.save()

                    #get item and update booking quantity
                    detail_item = item.cart_item
                    detail_item.booked_quantity = detail_item.booked_quantity+item.item_qty
                    detail_item.save()

                #delete carts
                Cart.objects.filter(cart_user=request.user).delete()

            messages.success(request, 'Permintaan anda berhasil diajukan dengan no: ' + transaction_no)
            send_notif('Terdapat permintaan baru dengan no: ' + transaction_no, request.user.profile.user_location_id)
            return redirect('permintaan')
        except Exception as e:
            messages.error(request, 'Terjadi kesalahan fatal, silakan hubungi administrator: ' + str(e))
            return redirect('permintaan_detail')
    except Cart.DoesNotExist:
        messages.error(request, 'Tidak ada barang yang akan diajukan')
    except Exception as ex:
        messages.error(request, 'Terjadi kesalahan fatal, silakan hubungi administrator: ' +str(ex))

    return redirect('home')

def send_notif(messages, location_id):
    conn = http.client.HTTPSConnection("api.pushover.net:443")
    key = 'USER_KEY'+str(location_id)
    user = config(key)
    conn.request("POST", "/1/messages.json",
                 urllib.parse.urlencode({
                     "token": config('APP_TOKEN'),
                     "user": user,
                     "title": "Simpatik",
                     "message": messages,
                 }), {"Content-type": "application/x-www-form-urlencoded"})
    conn.getresponse()

@method_decorator(login_required, name='dispatch')
class Riwayat(ListView):
    model = Transaction
    context_object_name = 'transactions'
    template_name = 'simpatik/riwayat.html'
    paginate_by = 10

    def get_queryset(self):
        queryset = Transaction.objects.filter(tr_created_by=self.request.user)\
            .order_by('transaction_sts', '-tr_created_dt')
        return queryset

@method_decorator(login_required, name='dispatch')
class RiwayatDetail(ListView):
    context_object_name = 'transaction_detail'
    template_name = 'simpatik/riwayat_detail.html'
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super(RiwayatDetail, self).get_context_data(**kwargs)
        context['transaction'] = Transaction.objects.get(pk=self.kwargs['pk'])
        return context

    def get_queryset(self):
        queryset = TransactionDetail.objects.filter(transaction_no=self.kwargs['pk'])
        return queryset


# Administrator
@method_decorator(login_required, name='dispatch')
class Request(LoginRequiredMixin, UserPassesTestMixin, ListView):
    def test_func(self):
        return self.request.user.is_staff

    model = Transaction
    context_object_name = 'transactions'
    template_name = 'simpatik/request.html'
    paginate_by = 10

    def get_queryset(self):
        diajukan = TransactionStatus.objects.get(status='diajukan')
        queryset = Transaction.objects.filter(tr_created_by__profile__user_location=self.request.user.profile.user_location,
                                              transaction_sts=diajukan).order_by('tr_created_dt')
        return queryset

@login_required()
@staff_member_required
def request_detail(request, pk):
    transaction = Transaction.objects.get(pk=pk)
    transaction_detail = TransactionDetail.objects.filter(transaction_no=transaction)
    return render(request, 'simpatik/request_detail.html',
                  {'transaction': transaction, 'transaction_detail': transaction_detail})

@login_required()
@staff_member_required
def finish_request(request, pk):
    try:
        trans = Transaction.objects.get(pk=pk)
        trans_dtl = TransactionDetail.objects.filter(transaction_no=trans)
        selesai = TransactionStatus.objects.get(status='selesai')
        try:
            with transaction.atomic():
                #transaction header
                trans.transaction_sts=selesai
                trans.tr_updated_by=request.user
                trans.tr_updated_dt=timezone.now()
                trans.save()

                #transaction detail
                for count, item in enumerate(trans_dtl, start=1):
                    #get item and update booking quantity
                    detail_item = item.item
                    detail_item.quantity = detail_item.quantity-item.detail_qty
                    detail_item.booked_quantity = detail_item.booked_quantity-item.detail_qty
                    detail_item.save()
            messages.success(request, 'Permintaan no: ' + trans.transaction_no +' telah selesai')
            return redirect('request')
        except Exception as e:
            messages.error(request, 'Terjadi kesalahan fatal, silakan hubungi administrator: ' + str(e))
            return redirect('request_detail', pk=pk)
    except Exception as ex:
        messages.error(request, 'Terjadi kesalahan fatal, silakan hubungi administrator: ' +str(ex))
    return redirect('request_detail', pk=pk)

@method_decorator(login_required, name='dispatch')
class ItemManagement(LoginRequiredMixin, UserPassesTestMixin, ListView):
    def test_func(self):
        return self.request.user.is_staff

    model = Item
    context_object_name = 'items'
    template_name = 'simpatik/item_management.html'
    paginate_by = 10

    # def get_context_data(self, **kwargs):
    #     kwargs['board'] = self.board
    #     return super().get_context_data(**kwargs)

    def get_queryset(self):
        queryset = Item.objects.filter(item_location=self.request.user.profile.user_location).\
            order_by('-item_updated_dt')
        return queryset

@login_required()
@staff_member_required()
def add_item(request):
    if request.method == 'POST':
        form = AddNewItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.item_location = request.user.profile.user_location
            item.item_created_by = request.user
            # item.starter = request.user
            item.save()
            messages.success(request, 'Barang berhasil ditambahkan')
            return redirect('item_management')
        else:
            messages.warning(request, 'Error, silakan perbaiki error berikut')
    else:
        form = AddNewItemForm()
    return render(request, 'simpatik/add_item.html', {'form': form})

@method_decorator(login_required, name='dispatch')
class ItemEditView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    def test_func(self):
        return self.request.user.is_staff

    model = Item
    fields = ('name', 'description', 'quantity', 'picture', )
    template_name = 'simpatik/edit_item.html'
    pk_url_kwarg = 'item_pk'
    context_object_name = 'item'

    # def get_queryset(self):
    #     queryset = super().get_queryset()
    #     return queryset.filter(created_by=self.request.user)

    def form_valid(self, form):
        item = form.save(commit=False)
        item.item_updated_by = self.request.user
        item.item_updated_dt = timezone.now()
        item.save()
        messages.success(self.request, 'Barang berhasil diubah')
        return redirect('item_management')

    def form_invalid(self, form):
        messages.warning(self.request, 'Error, silakan perbaiki error berikut')
        return super().form_invalid(form)

@login_required()
def v2home(request):
    boards = Board.objects.all()
    return render(request, 'simpatik/v2home.html', {'boards': boards})

# end

@method_decorator(login_required, name='dispatch')
class BoardListView(ListView):
    model = Board
    context_object_name = 'boards'
    template_name = 'forum/home.html'

@method_decorator(login_required, name='dispatch')
class TopicListView(ListView):
    model = Topic
    context_object_name = 'topics'
    template_name = 'forum/topics.html'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        kwargs['board'] = self.board
        return super().get_context_data(**kwargs)

    def get_queryset(self):
        self.board = get_object_or_404(Board, pk=self.kwargs.get('pk'))
        queryset = self.board.topics.order_by('-last_updated').annotate(replies=Count('posts') - 1)
        return queryset

@method_decorator(login_required, name='dispatch')
class PostListView(ListView):
    model = Post
    context_object_name = 'posts'
    template_name = 'forum/topic_posts.html'
    paginate_by = 2

    def get_context_data(self, **kwargs):
        session_key = 'viewed_topic_{}'.format(self.topic.pk)
        if not self.request.session.get(session_key, False):
            self.topic.views += 1
            self.topic.save()
            self.request.session[session_key]= True

        kwargs['topic'] = self.topic
        return super().get_context_data(**kwargs)

    def get_queryset(self):
        self.topic = get_object_or_404(Topic, board__pk=self.kwargs.get('pk'), pk=self.kwargs.get('topic_pk'))
        queryset = self.topic.posts.order_by('created_at')
        return queryset

# function based views ------------------------------------------>> paging example
# def board_topics(request, pk):
#     board = get_object_or_404(Board, pk=pk)
#     queryset = board.topics.order_by('-last_updated').annotate(replies=Count('posts')-1)
#     page = request.GET.get('page', 1)
#     paginator = Paginator(queryset, 20)
#     try:
#         topics = paginator.page(page)
#     except PageNotAnInteger:
#         # fallback to the first page
#         topics = paginator.page(1)
#     except EmptyPage:
#         # probably the user tried to add a page number
#         # in the url, so we fallback to the last page
#         topics = paginator.page(paginator.num_pages)
#     return render(request, 'forum/topics.html', {'board':board, 'topics':topics})
#
# def topic_posts(request, pk, topic_pk):
#     topic = get_object_or_404(Topic, board__pk=pk, pk=topic_pk)
#     topic.views += 1
#     topic.save()
#     return render(request, 'forum/topic_posts.html', {'topic': topic})

@login_required
def new_topic(request, pk):
    board = get_object_or_404(Board, pk=pk)
    if request.method == 'POST':
        form = NewTopicForm(request.POST)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.board = board
            topic.starter = request.user
            topic.save()
            post = Post.objects.create(
                message=form.cleaned_data.get('message'),
                topic=topic,
                created_by=request.user
            )
            return redirect('topic_posts', pk=pk, topic_pk=topic.pk)  # <- here
    else:
        form = NewTopicForm()
    return render(request, 'forum/new_topic.html', {'board': board, 'form': form})

@login_required
def reply_topic(request, pk, topic_pk):
    topic = get_object_or_404(Topic, board__pk=pk, pk=topic_pk)
    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.topic = topic
            post.created_by = request.user
            post.save()
            topic.last_updated = timezone.now()
            topic.save()

            topic_url = reverse('topic_posts', kwargs={'pk': pk, 'topic_pk': topic_pk})
            topic_post_url = '{url}?page={page}#{id}'.format(
                url=topic_url,
                id=post.pk,
                page=topic.get_page_count()
            )

            return redirect(topic_post_url)
    else:
        form = PostForm()
    return render(request, 'forum/reply_topic.html', {'topic': topic, 'form': form})

# @method_decorator(login_required, name='dispatch')
# class ReplyTopicUpdateView(CreateView):
#     model = Post
#     fields = ('message',)
#     template_name = 'forum/reply_topic.html'
#     pk_url_kwarg = 'post_pk'
#     context_object_name = 'post'
#
#     def get_queryset(self):
#         queryset = super().get_queryset()
#         return queryset.filter(created_by=self.request.user)
#
#     def form_valid(self, form):
#         post = form.save(commit=False)
#         post.updated_by = self.request.user
#         post.updated_at = timezone.now()
#         post.save()
#         return redirect('topic_posts', pk=post.topic.board.pk, topic_pk=post.topic.pk)

@method_decorator(login_required, name='dispatch')
class PostUpdateView(UpdateView):
    model = Post
    fields = ('message', )
    template_name = 'forum/edit_post.html'
    pk_url_kwarg = 'post_pk'
    context_object_name = 'post'

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(created_by=self.request.user)

    def form_valid(self, form):
        post = form.save(commit=False)
        post.updated_by = self.request.user
        post.updated_at = timezone.now()
        post.save()
        return redirect('topic_posts', pk=post.topic.board.pk, topic_pk=post.topic.pk)

