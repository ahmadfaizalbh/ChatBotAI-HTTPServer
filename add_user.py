from base import Session
from models import User
import getpass

session = Session()
username_not_valid = True
while username_not_valid:
    username = input("username:").strip()
    if len(username) < 4:
        print("username should be at least 4 letters")
    elif session.query(User).filter(
                        User.username == username
                    ).scalar() is None:
        username_not_valid = False
    else:
        print("username already exist, please try another username")

password_not_valid = True
while password_not_valid:
    password = getpass.getpass()
    cpassword = getpass.getpass(prompt="Confirm password:")
    if len(password) < 4:
        print("password should be at least 4 letters")
    elif password != cpassword:
        print("password  mismatch")
    else:
        password_not_valid = False
        user = User(username=username, password=password)
        session.add(user)
        session.commit()


session.close()
