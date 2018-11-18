from django import forms
from .models import Topic, Post, Item, Cart


class AddNewItemForm(forms.ModelForm):
    description = forms.CharField(
        widget=forms.Textarea(
            attrs={'rows': 5 }
        ),
        max_length=1000,
        help_text = 'The max length of the text is 1000.'
    )
    class Meta:
        model = Item
        fields = ['name', 'description', 'quantity', 'picture', ]

class AddNewItemCartForm(forms.ModelForm):
    class Meta:
        model = Cart
        fields = ['item_qty', ]

class NewTopicForm(forms.ModelForm):
    message = forms.CharField(
        widget=forms.Textarea(
            attrs={'rows': 5, 'placeholder': 'What is on your mind?'}
        ),
        max_length=4000,
        help_text = 'The max length of the text is 4000.'
    )

    class Meta:
        model = Topic
        fields = ['subject', 'message']

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['message', ]