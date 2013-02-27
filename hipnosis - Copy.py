import hashlib
import hmac
import jinja2
import os
import re
import webapp2
import json

from google.appengine.ext import db
from google.appengine.api import users

    
### GLOBALS

template_directory = os.path.join(os.path.dirname(__file__), 'templates')
jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_directory), autoescape=True)


hmac_message = os.path.join(os.path.dirname(__file__), 'secret/message')
f = open(hmac_message, 'r')
SECRET = f.read().strip()
f.close()


def render_template(template, **template_values):
    """Renders the given template with the given template_values"""
    # retrieve the html template
    t = jinja_environment.get_template(template)

    # render the html template with the given dictionary
    return t.render(template_values)


def create_salt():
    return hashlib.sha256(os.urandom(16)).hexdigest()


def create_salt_hash_pair(input, salt=None):
    if not salt:
        salt = create_salt()
    hash = hmac.new(SECRET, salt + input, hashlib.sha256).hexdigest()
    return "%s|%s" % (salt, hash)


def validate_salt_hash_pair(input, hash):
    salt = hash.split('|')[0]
    return hash == create_salt_hash_pair(input, salt)


def create_value_salt_hash_triplet(value, salt=None):
    if not salt:
        salt = create_salt()
    hash = hmac.new(SECRET, str(value) + salt).hexdigest()
    return "%s|%s|%s" % (value, salt, hash)


def validate_value_salt_hash_triplet(hash):
    value = hash.split('|')[0]
    salt = hash.split('|')[1]
    if hash == create_value_salt_hash_triplet(value, salt):
        return value

        
### CLASSES

class Habit(db.Model):
    """Models a habit."""
    title = db.StringProperty(required = True)
    behavior = db.TextProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True)
    last_modified = db.DateTimeProperty(auto_now = True)

    def render(self):
        self._render_text = self.behavior.replace('\n', '<br>')
        return render_template("habit.html", habit = self)

class Person(db.Model):
    """Models a person."""
    user_id = db.StringProperty()

    
### HANDLERS

class BaseHandler(webapp2.RequestHandler):
    """Represents a handler which contains functions necessary for multiple
    handlers"""
    def write_template(self, template, **template_values):
        """Function to write out the given template with the given
        template_values"""
        self.response.out.write(render_template(template, **template_values))

    def set_cookie(self, name, value):
        """Function to set an http cookie"""
        self.response.headers.add_header('Set-Cookie', '%s=%s; Path=/' % (name, value))

    def get_cookie(self, name):
        """Function to get the value of a named parameter of an http cookie"""
        return self.request.cookies.get(name)

    def set_encrypted_cookie(self, name, value):
        """Function to set an http cookie"""
        self.response.headers.add_header('Set-Cookie', '%s=%s; Path=/' % (name, create_value_salt_hash_triplet(value)))

    def get_encrypted_cookie(self, name):
        """Function to get the value of a named parameter of an http cookie"""
        return validate_value_salt_hash_triplet(self.request.cookies.get(name))
    
        
class MainPage(BaseHandler):
    def get(self):   
        user = users.get_current_user()
        
        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
            person = db.GqlQuery("SELECT * FROM Person " + 
                                 "WHERE user_id = :1 ",
                                 user.user_id())
            person = person.get()
            
            if not person:
                person = Person(user_id = user.user_id())
                person.put()
            
            habits = db.GqlQuery("SELECT * FROM Habit " + 
                                 "WHERE ANCESTOR IS :1 " + 
                                 "ORDER BY created DESC ",
                                 person)
            template_values = {
                'habits': habits,
                'url': url,
                'url_linktext': url_linktext
            }            
            self.write_template('hipnosis.html', **template_values)
            

        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
            template_values = {
                'url': url,
                'url_linktext': url_linktext
            }
        
            self.write_template('base.html', **template_values)
        
class HabitPage(BaseHandler):
    def get(self, habit_id):
        user = users.get_current_user()
        
        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        person = db.GqlQuery("SELECT __key__ FROM Person " + 
                             "WHERE user_id = :1 ",
                             user.user_id())
        person = person.get()
        
        if not person:
            person = Person(user_id = user.user_id())
            person.put()
        
        # key = db.Key.from_path('Habit', int(habit_id), parent = person)
        habit = Habit.get_by_id(int(habit_id), parent = person)

        
        # if not habit:
            # self.error(404)
            # return

        self.write_template("permalink.html", habit = habit)

        
class NewHabit(BaseHandler):
    def get(self):
        user = users.get_current_user()        
        
        if user:
            self.write_template("newhabit.html")
        else:
            self.redirect(users.create_login_url(self.request.uri))

    def post(self):
        user = users.get_current_user()
        
        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        person = db.GqlQuery("SELECT * FROM Person " + 
                             "WHERE user_id = :1 ",
                             user.user_id())
        person = person.get()
        
        if not person:
            person = Person(user_id = user.user_id())
            person.put()
        
        if not user:
            self.redirect('/')

        title = self.request.get('title')
        behavior = self.request.get('behavior')

        if title and behavior:
            h = Habit(parent = person, title = title, behavior = behavior)
            hput = h.put()
            self.response.out.write(h.key().id())
            #self.redirect('/habit/%s' % str(h.key().id()))
        else:
            error = "title and behavior, please!"
            self.write_template("newhabit.html", title=title, behavior=behavior, error=error)
            
### ROUTER
        
app = webapp2.WSGIApplication([('/', MainPage),
                               ('/habit/([0-9]+)', HabitPage),
                               ('/newhabit', NewHabit)
                              ],
                              debug=True)

# app = webapp2.WSGIApplication([('/', MainPage)], debug=True)
