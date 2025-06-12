from django.urls import path
from . import views

app_name = 'wiki'

urlpatterns = [
    path('', views.wiki, name='wiki'),
    path('search/', views.search, name='search'),
    path('all/', views.all_wiki_pages, name='all_pages'),
    path('create/', views.page_create, name='page_create'),
    path('<slug:slug>/', views.wiki_page, name='wiki_page'),
    path('<slug:slug>/edit/', views.page_edit, name='page_edit'),
    path('<slug:slug>/delete/', views.page_delete, name='page_delete'),
    path('<slug:slug>/upload/', views.page_upload_file, name='page_upload_file'),
    path('<slug:slug>/delete_file/<int:file_id>/', views.page_delete_file, name='page_delete_file'),
    path('<slug:slug>/download_file/<int:file_id>/', views.page_download_file, name='page_download_file'),

    path('<slug:parent_slug>/exam/create/', views.exam_create, name='exam_create'),
    path('<slug:parent_slug>/exam/<slug:exam_slug>/', views.exam, name='exam'),
    path('<slug:parent_slug>/exam/<slug:exam_slug>/edit/', views.exam_edit, name='exam_edit'),
    path('<slug:parent_slug>/exam/<slug:exam_slug>/delete/', views.exam_delete, name='exam_delete'),
    path('<slug:parent_slug>/exam/<slug:exam_slug>/download/', views.exam_download, name='exam_download'),
]