from http.server import BaseHTTPRequestHandler, HTTPServer
from handler import Chat, db_session
from urllib.parse import parse_qs, urlparse
from base import Session
from chatbot import register_call
import wikipedia
import warnings
import cgi
import http
from models import User, Session as UserSession, Conversation
from sqlalchemy.orm.exc import NoResultFound
import json
warnings.filterwarnings("ignore")


@register_call("whoIs")
def who_is(session, query):
    try:
        return wikipedia.summary(query)
    except Exception:
        for new_query in wikipedia.search(query):
            try:
                return wikipedia.summary(new_query)
            except Exception:
                pass
    return "I don't know about "+query


chat = Chat("Example.template")

router = {}


def action(path, method=None, login_required=True):
    def wrapper(fun):
        nonlocal method
        if method is None:
            method=["GET", "POST", "PUT", "DELETE"]
        elif isinstance(method,(str, bytes)):
            method=[str(method)]
        elif not isinstance(method,(list, tuple)):
            raise TypeError("method should be str or list of str")
        fun.login_required = login_required
        for m in method:
            router[(path, m)] = fun.__name__
        return fun
    return wrapper


def string(data):
    if isinstance(data, bytes):
        return data.decode("utf-8")
    return str(data)


class Handler(BaseHTTPRequestHandler):

    @property
    def GET(self):
        if not hasattr(self, "_GET"):
            self._GET = {
                string(key): string(val[0])
                for key, val in parse_qs(urlparse(self.path).query, keep_blank_values=True).items()}
        return self._GET

    @property
    def POST(self):
        if not hasattr(self, "_POST"):
            ctype, pdict = cgi.parse_header(self.headers['content-type'])
            if ctype == 'multipart/form-data':
                data = cgi.parse_multipart(self.rfile, pdict)
            elif ctype == 'application/x-www-form-urlencoded':
                length = int(self.headers['content-length'])
                data = parse_qs(self.rfile.read(length), keep_blank_values=True)
            else:
                data = {}
            self._POST = {string(key): string(val[0]) for key, val in data.items()}
        return self._POST

    @action("/web_hook", method=["GET", "POST"])
    def web_hook(self):
        user_id = self.session.user
        if not chat.has_session(user_id):
            # New User
            chat.start_new_session(user_id)
        if self._method == "POST":
            message = self.POST.get("message")
            last_message_id = self.POST.get("last_message_id", 0)
            if not message:
                self.send_response(400)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(b"message missing")
                return
            chat.respond(message, user_id)
            messages = db_session.session.query(Conversation).filter(
                Conversation.sender == user_id,
                Conversation.id > int(last_message_id))
        else:
            messages = db_session.session.query(Conversation).filter(
                Conversation.sender == user_id)
        messages = messages.order_by(Conversation.id.asc())

        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        data = {
            "status": "Success",
            "messages": [{"id": msg.id,
                          "text": msg.message,
                          "created": msg.created.strftime('%Y-%m-%d %H:%M:%S'),
                          "by": "bot" if msg.bot else "user"
                          } for msg in messages]
        }
        self.wfile.write(json.dumps(data).encode('utf-8'))

    @action("/", method="GET")
    def index(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        with open("htmls/index.html", "rb") as html:
            self.wfile.write(html.read())

    @action("/login", method="GET", login_required=False)
    def login_page(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        # for morsel in cookie.values():
        #     self.send_header("Set-Cookie", morsel.OutputString())
        self.end_headers()
        with open("htmls/login.html", "rb") as html:
            self.wfile.write(html.read())

    @action("/login", method="POST", login_required=False)
    def login(self):
        username = self.POST.get("username")
        password = self.POST.get("password")
        try:
            user = db_session.session.query(User).filter(
                User.username == username,
                User.pass_hash == User.hash_password(password),
            ).one()
        except NoResultFound:
            self.send_response(302)
            self.send_header('Location', "/login")
            self.end_headers()
            return
        cookie = http.cookies.SimpleCookie()
        user_session = UserSession(user=username)
        db_session.session.add(user_session)
        db_session.session.commit()
        cookie["session"] = f"{user_session.id}-{user_session.uid}"
        self.send_response(302)
        for data in cookie.values():
            self.send_header("Set-Cookie", data.OutputString())
        self.send_header('Location', "/")
        self.end_headers()

    def get_session(self):
        try:
            # close DB session for thread
            cookie = http.cookies.SimpleCookie(self.headers.get('Cookie'))
            if cookie.get('session'):
                id, uid = cookie.get('session').value.split("-", 1)
                try:
                    return db_session.session.query(UserSession).filter(
                        UserSession.id == int(id),
                        UserSession.uid == uid,
                    ).one()
                except NoResultFound:
                    self.send_response(302)
                    self.send_header('Location', "/login")
                    self.end_headers()
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.wfile.write(f"<h1>Error: {e}</h1>".encode('utf-8'))

    def request_handler(self, method):
        db_session.session = Session()
        self._method = method
        function_name = router.get((urlparse(self.path).path, method))
        if function_name is None:
            self.send_response(404)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.wfile.write(f"<h1>404: Page Not Found</h1>".encode('utf-8'))
            return
        function = getattr(self, function_name)
        if hasattr(function, "login_required") and function.login_required:
            self.session = self.get_session()
            if not self.session:
                self.send_response(302)
                self.send_header('Location', "/login")
                self.end_headers()
                return
        function()
        db_session.session.close()

    def do_POST(self):
        self.request_handler("POST")

    def do_GET(self):
        self.request_handler("GET")

    def do_PUT(self):
        self.request_handler("PUT")

    def do_PATCH(self):
        self.request_handler("PATCH")

    def do_DELETE(self):
        self.request_handler("DELETE")


PORT = 8000


server = HTTPServer(('localhost', PORT), Handler)
print('Started http server')
try:
    server.serve_forever()
except KeyboardInterrupt:
    print('^C received, shutting down server')
    server.socket.close()
