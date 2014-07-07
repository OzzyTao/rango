from django.shortcuts import render_to_response, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext
from rango.models import Category, Page, UserProfile
from rango.forms import CategoryForm, PageForm, UserForm, UserProfileForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from datetime import datetime
from rango.bing_search import run_query
# Create your views here.

def index(request):
	context=RequestContext(request)
	category_list=Category.objects.order_by('-likes')[:5]
	page_list=Page.objects.order_by('-views')[:5]
	cat_list=get_category_list()
	context_dict = {'categories':category_list,'pages':page_list,'cat_list':cat_list}
	for category in category_list:
		category.url=category.name.replace(' ','_')
	if request.session.get('last_visit'):
		last_visit_time = request.session.get('last_visit')
		visits = request.session.get('visits',0)
		if (datetime.now()-datetime.strptime(last_visit_time[:-7],"%Y-%m-%d %H:%M:%S")).days>0:
			request.session['visits']=visits+1
			request.session['last_visit']=str(datetime.now())
	else:
		request.session['last_visit']=str(datetime.now())
		request.session['visits']=1
	return render_to_response('rango/index.html',context_dict,context)

def about(request):
	context=RequestContext(request)
	if request.session.get('visits'):
		count = request.session.get('visits')
	else:
		count = 0
	return render_to_response('rango/about.html',
		{'message':"Rango Says: Here is the about page.",
		'visits':count},
		context)

def category(request,category_name_url):
	context=RequestContext(request)
	category_name=category_name_url.replace('_',' ')
	context_dict={'category_name':category_name,'category_name_url':category_name_url}
	cat_list=get_category_list()
	context_dict['cat_list']=cat_list
	try:
		category=Category.objects.get(name__iexact=category_name)
		pages=Page.objects.filter(category=category).order_by('-views')
		context_dict['category']=category
		context_dict['pages']=pages
	except Category.DoesNotExist:
		pass
	if request.method=="POST":
		query=request.POST['query'].strip()
		if query:
			result_list=run_query(query)
			context_dict['result_list']=result_list
	return render_to_response('rango/category.html',context_dict,context)

@login_required
def add_category(request):
	context=RequestContext(request)
	if request.method=='POST':
		form=CategoryForm(request.POST)
		if form.is_valid():
			form.save(commit=True)
			return index(request)
		else:
			print form.errors
	else:
		form=CategoryForm()
	return render_to_response('rango/add_category.html',{'form':form},context)

@login_required
def add_page(request,category_name_url):
	context=RequestContext(request)
	category_name=category_name_url.replace('_',' ')
	if request.method=='POST':
		form=PageForm(request.POST)
		if form.is_valid():
			page=form.save(commit=False)
			try:
				cat=Category.objects.get(name=category_name)
				page.category=cat
			except Category.DoesNotExist:
				return render_to_response('rango/add_category.html',{},context)
			page.views=0
			page.save()
			return category(request,category_name_url)
		else:
			print form.errors
	else:
		form=PageForm()
	return render_to_response('rango/add_page.html',
		{'category_name_url':category_name_url,
		'category_name':category_name,
		'form':form},context)

def register(request):
	context=RequestContext(request)
	registered=False
	if request.method=='POST':
		user_form=UserForm(data=request.POST)
		profile_form=UserProfileForm(data=request.POST)
		if user_form.is_valid() and profile_form.is_valid():
			user=user_form.save()
			user.set_password(user.password)
			user.save()
			profile=profile_form.save(commit=False)
			profile.user=user
			if 'picture' in request.FILES:
				profile.picture = request.FILES['picture']
			profile.save()
			registered=True
		else:
			print user_form.errors, profile_form.errors
	else:
		user_form=UserForm()
		profile_form=UserProfileForm()

	return render_to_response('rango/register.html',
		{'user_form':user_form,'profile_form':profile_form,'registered':registered},
		context)

def user_login(request):
	context=RequestContext(request)
	errors=[]
	if request.method=='POST':
		username = request.POST['username']
		password=request.POST['password']

		user=authenticate(username=username,password=password)
		if user:
			if user.is_active:
				login(request,user)
				return HttpResponseRedirect('/rango/')
			else:
				return HttpResponse("Your Rango account is disabled.")
		else:
			print "Invalid login details: {0}, {1}".format(username,password)
			errors.append("Invalid login details supplied.")
	return render_to_response('rango/login.html',{'errors':errors},context)

@login_required
def restricted(request):
	return HttpResponse("Since you are logged in, you can see this text!")

@login_required
def user_logout(request):
	logout(request)
	return HttpResponseRedirect('/rango/')
@login_required
def profile(request):
	context=RequestContext(request)
	cat_list=get_category_list()
	context_dict={'cat_list':cat_list}
	u=User.objects.get(username=request.user)
	try:
		up=UserProfile.objects.get(user=u)
	except:
		up=None
	context_dict['user']=u
	context_dict['userprofile']=up
	return render_to_response('rango/profile.html',context_dict,context)

@login_required
def like_category(request):
	context=RequestContext(request)
	cat_id=None
	likes=0
	if request.method=='GET':
		cat_id=request.GET['category_id']
	if cat_id:
		category=Category.objects.get(id=int(cat_id))
		if category:
			likes=category.likes+1
			category.likes=likes
			category.save()
	return HttpResponse(likes)

def track_url(request):
	context=RequestContext(request)
	page_id =None
	url='/rango/'
	if request.method=='GET':
		if 'page_id' in request.GET:
			page_id=request.GET['page_id']
			try:
				page=Page.objects.get(id=page_id)
				page.views+=1
				page.save()
				url=page.url
			except:
				pass
	return redirect(url)

def suggest_category(request):
	context=RequestContext(request)
	cat_list=[]
	starts_with=''
	if request.method=='GET':
		starts_with=request.GET['suggestion']
	cat_list=get_category_list(8,starts_with)
	return render_to_response('rango/category_list.html',{'cat_list':cat_list},context)

@login_required
def auto_add_page(request):
	context=RequestContext(request)
	page_list=[]
	if request.method=='GET':
		title=request.GET['title']
		url=request.GET['url']
		catid=request.GET['catid']
		category=Category.objects.get(id=int(catid))
		if category and title:
			new_page=Page.objects.get_or_create(category=category,title=title,url=url)
		page_list=Page.objects.filter(category=category).order_by('-views')
	return render_to_response('rango/page_list.html',{'pages':page_list},context)
	


def get_category_list(max_results=0,starts_with=''):
	cat_list=[]
	if starts_with:
		cat_list=Category.objects.filter(name__istartswith=starts_with)
	else:
		cat_list=Category.objects.all()
	if max_results>0:
		if len(cat_list) > max_results:
			cat_list=cat_list[:max_results]
	for category in cat_list:
		category.url=category.name.replace(' ','_')
	return cat_list

