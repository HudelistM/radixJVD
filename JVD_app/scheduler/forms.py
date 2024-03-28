from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Employee

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['name', 'surname', 'role', 'group']