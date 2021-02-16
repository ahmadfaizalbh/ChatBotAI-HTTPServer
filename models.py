from sqlalchemy import Column, Text, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from datetime import datetime
from base import Base, engine
import hashlib
from settings import HASH_SALT
import uuid


class User(Base):
    __tablename__ = 'users'

    username = Column(Text, primary_key=True)
    pass_hash = Column(Text)

    def __init__(self, username, password):
        self.username = username
        self.pass_hash = self.hash_password(password)

    @staticmethod
    def hash_password(password):
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                                   HASH_SALT.encode('utf-8'), 100000).hex()


class Session(Base):
    __tablename__ = 'session'

    id = Column(Integer, primary_key=True)
    user = Column(Text, ForeignKey('users.username'), nullable=False)
    uid = Column(Text)
    created = Column(DateTime)

    def __init__(self, user):
        self.user = user
        self.uid = str(uuid.uuid4())
        self.created = datetime.now()


class Sender(Base):
    __tablename__ = 'senders'

    sender_id = Column(Text, primary_key=True)
    topic = Column(Text)

    def __init__(self, sender_id, topic=""):
        self.sender_id = sender_id
        self.topic = topic


class Memory(Base):
    __tablename__ = 'memories'
    __table_args__ = (UniqueConstraint('sender', 'key'),)

    id = Column(Integer, primary_key=True)
    sender = Column(Text, ForeignKey('senders.sender_id'), nullable=False)
    key = Column(Text)
    value = Column(Text)

    def __init__(self, sender, key, value):
        self.sender = sender
        self.key = key
        self.value = value


class Conversation(Base):
    __tablename__ = 'conversations'

    id = Column(Integer, primary_key=True)
    sender = Column(Text, ForeignKey('senders.sender_id'), nullable=False)
    message = Column(Text)
    created = Column(DateTime)
    bot = Column(Boolean)

    def __init__(self, sender, message, bot=True):
        self.sender = sender
        self.message = message
        self.created = datetime.now()
        self.bot = bot


if __name__ == "__main__":
    Base.metadata.create_all(engine)
