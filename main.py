import jinja2
import os
import webapp2

from google.appengine.ext import db
from google.appengine.api import users


### GLOBALS

template_directory = os.path.join(os.path.dirname(__file__), 'templates')
jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_directory), autoescape=True)


def newline_to_html(text):
    return text.replace('\n', '<br>')
   
def render_template(template, **template_values):
    """Renders the given template with the given template_values"""
    # retrieve the html template
    t = jinja_environment.get_template(template)

    # render the html template with the given dictionary
    return t.render(template_values)

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


class MainPage(BaseHandler):
    def get(self):
        user = users.get_current_user()

        if user:
            # grab current user from datastore or create new user
            person_query = db.GqlQuery("SELECT * FROM Person " +
                "WHERE user_id = :1 ",
                user.user_id())
            person_entity = person_query.get()

            if not person_entity:
                person_entity = Person(user_id = user.user_id())
                person_entity.put()

            # grab current user's habits from datastore
            habits_query = db.GqlQuery("SELECT * FROM Habit " +
                "WHERE ANCESTOR IS :1 " +
                "ORDER BY created DESC ",
                person_entity)
            
            # write out the current user's habits
            template_values = {
                'habits': habits_query,
                'login_href': users.create_logout_url(self.request.uri),
                'login_content': 'Logout'
            }
            
            self.write_template('habits.html', **template_values)
        else:
            template_values = {
                'login_href': users.create_login_url(self.request.uri),
                'login_content': 'Login'
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
