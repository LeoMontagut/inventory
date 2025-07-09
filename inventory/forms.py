from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Product, Category, UserProfile

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            # Crear perfil automáticamente
            UserProfile.objects.create(user=user)
        return user

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['business_name', 'business_logo', 'address', 'city', 'phone', 'email']
        widgets = {
            'business_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'business_logo': forms.FileInput(attrs={'class': 'form-control'}),
        }

class PDFConfigForm(forms.Form):
    client_name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre del cliente (opcional)'
        }),
        label="Cliente"
    )

    creation_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Fecha de creación",
        help_text="Si no se especifica, se usará la fecha actual"
    )

    valid_until = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Válido hasta (opcional)"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Establecer fecha actual como valor por defecto
        from datetime import datetime
        self.fields['creation_date'].initial = datetime.now().date()

class ProductForm(forms.ModelForm):
    category_name = forms.CharField(max_length=100, required=False,
                                   help_text="Escribe aquí para crear una nueva categoría")

    class Meta:
        model = Product
        fields = ['name', 'category', 'price', 'stock_quantity']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['category'].queryset = Category.objects.filter(user=self.user)
            # Hacer el campo category no requerido si se va a crear una nueva categoría
            self.fields['category'].required = False
            self.fields['category'].empty_label = "Selecciona una categoría existente (opcional)"

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        category_name = cleaned_data.get('category_name')

        # Validar que se proporcione al menos una categoría
        if not category and not category_name:
            raise forms.ValidationError(
                'Debes seleccionar una categoría existente o crear una nueva.'
            )

        return cleaned_data

    def save(self, commit=True):
        product = super().save(commit=False)

        # Si se proporcionó un nombre de categoría nueva, crearla
        if self.cleaned_data.get('category_name') and self.user:
            category, created = Category.objects.get_or_create(
                name=self.cleaned_data['category_name'],
                user=self.user
            )
            product.category = category

        if commit:
            product.save()
        return product

class AddToCartForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, initial=1, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    custom_price = forms.DecimalField(max_digits=10, decimal_places=2, required=False,
                                     widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))
