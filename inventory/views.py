from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import datetime, date
import os
from PIL import Image as PILImage

from .models import Product, Category, Cart, CartItem, UserProfile
from .forms import CustomUserCreationForm, ProductForm, AddToCartForm, UserProfileForm, PDFConfigForm

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, '¡Cuenta creada exitosamente!')
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, 'Has cerrado sesión exitosamente.')
    return redirect('login')

@login_required
def profile_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil actualizado exitosamente!')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile)

    return render(request, 'inventory/profile.html', {'form': form, 'profile': profile})

@login_required
def home(request):
    products = Product.objects.filter(user=request.user)
    categories = Category.objects.filter(user=request.user)

    # Filtros
    category_filter = request.GET.get('category')
    search_query = request.GET.get('search')

    if category_filter:
        products = products.filter(category_id=category_filter)

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(category__name__icontains=search_query)
        )

    # Obtener carrito
    cart, created = Cart.objects.get_or_create(user=request.user)

    context = {
        'products': products,
        'categories': categories,
        'selected_category': category_filter,
        'search_query': search_query,
        'cart_items_count': cart.get_items_count(),
    }
    return render(request, 'inventory/home.html', context)

@login_required
def product_list(request):
    products = Product.objects.filter(user=request.user)
    return render(request, 'inventory/product_list.html', {'products': products})

@login_required
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, user=request.user)
        if form.is_valid():
            product = form.save(commit=False)
            product.user = request.user
            product.save()
            messages.success(request, 'Producto agregado exitosamente!')
            return redirect('product_list')
    else:
        form = ProductForm(user=request.user)
    return render(request, 'inventory/add_product.html', {'form': form})

@login_required
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto actualizado exitosamente!')
            return redirect('product_list')
    else:
        form = ProductForm(instance=product, user=request.user)
    return render(request, 'inventory/edit_product.html', {'form': form, 'product': product})

@login_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk, user=request.user)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Producto eliminado exitosamente!')
        return redirect('product_list')
    return render(request, 'inventory/delete_product.html', {'product': product})

@login_required
def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk, user=request.user)
    cart, created = Cart.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = AddToCartForm(request.POST)
        if form.is_valid():
            quantity = form.cleaned_data['quantity']
            custom_price = form.cleaned_data['custom_price']

            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                defaults={'quantity': quantity, 'custom_price': custom_price}
            )

            if not created:
                cart_item.quantity += quantity
                if custom_price:
                    cart_item.custom_price = custom_price
                cart_item.save()

            messages.success(request, f'{product.name} agregado al carrito!')
            return redirect('home')
    else:
        form = AddToCartForm()

    return render(request, 'inventory/add_to_cart.html', {'form': form, 'product': product})

@login_required
def cart_view(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    pdf_form = PDFConfigForm()
    return render(request, 'inventory/cart.html', {'cart': cart, 'pdf_form': pdf_form})

@login_required
def update_cart_item(request, pk):
    cart_item = get_object_or_404(CartItem, pk=pk, cart__user=request.user)

    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        custom_price = request.POST.get('custom_price')

        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.custom_price = float(custom_price) if custom_price else None
            cart_item.save()
            messages.success(request, 'Carrito actualizado!')
        else:
            cart_item.delete()
            messages.success(request, 'Producto eliminado del carrito!')

    return redirect('cart')

@login_required
def remove_from_cart(request, pk):
    cart_item = get_object_or_404(CartItem, pk=pk, cart__user=request.user)
    cart_item.delete()
    messages.success(request, 'Producto eliminado del carrito!')
    return redirect('cart')

@login_required
def clear_cart(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart.items.all().delete()
    messages.success(request, 'Carrito vaciado!')
    return redirect('cart')

@login_required
def generate_pdf(request):
    cart, created = Cart.objects.get_or_create(user=request.user)

    if not cart.items.exists():
        messages.error(request, 'El carrito está vacío!')
        return redirect('cart')

    # Obtener datos del formulario PDF
    pdf_form = PDFConfigForm(request.POST or None)
    client_name = ""
    creation_date = datetime.now().date()
    valid_until = None

    if request.method == 'POST' and pdf_form.is_valid():
        client_name = pdf_form.cleaned_data.get('client_name', '')
        creation_date = pdf_form.cleaned_data.get('creation_date') or datetime.now().date()
        valid_until = pdf_form.cleaned_data.get('valid_until')

    # Obtener perfil del usuario
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    # Crear PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm,
                           leftMargin=2*cm, rightMargin=2*cm)

    # Estilos
    styles = getSampleStyleSheet()
    
    # Estilo para el título principal
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=28,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2c3e50')  # Azul oscuro
    )

    # Estilo para información del negocio
    business_style = ParagraphStyle(
        'BusinessInfo',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=6,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#34495e')  # Gris oscuro
    )

    # Estilo para información del documento
    info_style = ParagraphStyle(
        'InfoStyle',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=4,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#7f8c8d')  # Gris medio
    )

    story = []

    # Marca de agua con logo (si existe)
    if profile.business_logo:
        try:
            logo_path = profile.business_logo.path
            # Crear marca de agua transparente en la esquina superior izquierda
            watermark = Image(logo_path, width=4*cm, height=4*cm)
            watermark.drawHeight = 4*cm
            watermark.drawWidth = 4*cm
            # Hacer transparente (alpha = 0.3)
            watermark.opacity = 0.3
            story.append(watermark)
        except:
            pass

    # Información del negocio
    business_info = []
    if profile.business_name:
        business_info.append(f"<b>{profile.business_name}</b>")
    if profile.address:
        business_info.append(profile.address)
    if profile.city:
        business_info.append(profile.city)
    if profile.phone:
        business_info.append(f"Tel: {profile.phone}")
    if profile.email:
        business_info.append(profile.email)

    business_text = "<br/>".join(business_info) if business_info else "Información del negocio"
    story.append(Paragraph(business_text, business_style))
    story.append(Spacer(1, 30))

    # Información del documento
    story.append(Paragraph(f"<b>Fecha:</b> {creation_date.strftime('%d/%m/%Y')}", info_style))

    # Solo mostrar cliente si se proporcionó
    if client_name.strip():
        story.append(Paragraph(f"<b>Cliente:</b> {client_name}", info_style))

    # Solo mostrar "válido hasta" si se proporcionó
    if valid_until:
        story.append(Paragraph(f"<b>Válido hasta:</b> {valid_until.strftime('%d/%m/%Y')}", info_style))

    story.append(Spacer(1, 25))

    # Tabla de productos con índice
    data = [['#', 'Producto', 'Cantidad', 'Precio Unitario', 'Subtotal']]

    for index, item in enumerate(cart.items.all(), 1):
        data.append([
            str(index),
            item.product.name,
            str(item.quantity),
            f"${item.get_price():.2f}",
            f"${item.get_subtotal():.2f}"
        ])

    # Fila del total
    data.append(['', '', '', 'TOTAL:', f"${cart.get_total():.2f}"])

    # Crear tabla con columnas coloreadas
    table = Table(data, colWidths=[1*cm, 7*cm, 2*cm, 3*cm, 3*cm])
    
    # Definir colores
    header_color = colors.HexColor('#3498db')  # Azul
    row_color = colors.HexColor('#ecf0f1')     # Gris claro
    total_color = colors.HexColor('#e74c3c')   # Rojo
    
    table.setStyle(TableStyle([
        # Encabezado con color
        ('BACKGROUND', (0, 0), (-1, 0), header_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -2), 'LEFT'),  # Nombres de productos alineados a la izquierda
        ('ALIGN', (0, 1), (0, -2), 'CENTER'),  # Índices centrados

        # Filas alternadas con color
        ('BACKGROUND', (0, 1), (-1, -2), row_color),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [row_color, colors.white]),

        # Fila del total con color
        ('BACKGROUND', (0, -1), (-1, -1), total_color),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),

        # Bordes más delgados
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#2980b9')),

        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))

    story.append(table)

    # Construir PDF
    doc.build(story)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')

    # Nombre del archivo con información adicional
    filename_parts = ["cotizacion", datetime.now().strftime("%Y%m%d_%H%M%S")]
    if client_name.strip():
        # Limpiar nombre del cliente para el filename
        clean_client_name = "".join(c for c in client_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_client_name = clean_client_name.replace(' ', '_')
        if clean_client_name:
            filename_parts.insert(1, clean_client_name)

    filename = "_".join(filename_parts) + ".pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response
