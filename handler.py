from chatbot import Chat as ChatBot
from models import Conversation, Memory, Sender
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
import settings
import threading
from base import Session

db_session = threading.local()


class UserMemory:

    def __init__(self, sender_id, *args, **kwargs):
        self.sender_id = sender_id
        self.update(*args, **kwargs)

    def __get_memory__(self, key):
        memory = db_session.session.query(Memory).filter(Memory.sender == self.sender_id,
                                                         Memory.key == key.lower())
        try:
            return memory.one()
        except MultipleResultsFound:
            return memory.first()
        except NoResultFound:
            raise KeyError(key)

    def __getitem__(self, key):
        return self.__get_memory__(key).value

    def __setitem__(self, key, val):
        try:
            memory = self.__get_memory__(key)
            memory.value = val
            memory.save()
            db_session.session.commit()
        except KeyError:
            memory = Memory(sender=self.sender_id, key=key.lower(), value=val)
            db_session.session.add(memory)
            db_session.session.commit()

    def update(self, *args, **kwargs):
        for k, v in dict(*args, **kwargs).items():
            self[k] = v

    def __delitem__(self, key):
        self.__get_memory__(key).delete()
        db_session.session.commit()

    def __contains__(self, key):
        return db_session.session.query(Memory).filter(Memory.sender == self.sender_id,
                                                       Memory.key == key.lower()).scalar() is not None


class UserConversation:

    def __init__(self, sender_id, *args):
        self.sender_id = sender_id
        self.extend(list(*args))

    def get_sender(self):
        return db_session.session.query(Sender).filter(Sender.sender_id == self.sender_id).one()

    def get_conversation(self, index, *args):
        conversations = db_session.session.query(Conversation).filter(
            Conversation.sender == self.sender_id, *args)
        if index < 0:
            index = -index - 1
            conversations = conversations.order_by(Conversation.id.desc())
        else:
            conversations = conversations.order_by(Conversation.id.asc())
        try:
            return conversations.offset(index).limit(1).one()
        except:
            raise IndexError("list index out of range")

    def get_bot_message(self, index):
        return self.get_conversation(index, Conversation.bot == True).message

    def get_user_message(self, index):
        return self.get_conversation(index, Conversation.bot == False).message

    def __getitem__(self, index):
        return self.get_conversation(index).message

    def __setitem__(self, index, message):
        conversation = self.get_conversation(index)
        conversation.message = message
        db_session.session.commit()

    def extend(self, items):
        for item in items:
            self.append(item)

    def append(self, message, **kwargs):
        conversation = Conversation(sender=self.sender_id, message=message, **kwargs)
        db_session.session.add(conversation)
        db_session.session.commit()

    def append_bot_message(self, message):
        self.append(message, bot=True)

    def append_user_message(self, message):
        self.append(message, bot=False)

    def __delitem__(self, index):
        self.get_conversation(index).delete()
        db_session.session.commit()

    def pop(self):
        try:
            conversation = self.get_conversation(-1)
            message = conversation.message
            conversation.delete()
            db_session.session.commit()
            return message
        except IndexError:
            raise IndexError("pop from empty list")

    def __contains__(self, message):
        return db_session.session.query(Conversation).filter(
            Conversation.sender == self.sender_id).scalar() is not None


class UserTopic:

    def __init__(self, *args, **kwargs):
        self.update(*args, **kwargs)

    def __get_sender__(self, sender_id):
        try:
            return db_session.session.query(Sender).filter(Sender.sender_id == sender_id).one()
        except NoResultFound:
            raise KeyError(sender_id)

    def __getitem__(self, sender_id):
        return self.__get_sender__(sender_id).topic

    def __setitem__(self, sender_id, topic):
        try:
            sender = self.__get_sender__(sender_id)
            sender.topic = topic
            db_session.session.commit()
        except KeyError:
            sender = Sender(sender_id=sender_id, topic=topic)
            db_session.session.add(sender)
            db_session.session.commit()

    def update(self, *args, **kwargs):
        for k, v in dict(*args, **kwargs).items():
            self[k] = v

    def __delitem__(self, sender_id):
        self.__get_sender__(sender_id).delete()
        db_session.session.commit()

    def __contains__(self, sender_id):
        return db_session.session.query(Sender).filter(
            Sender.sender_id == sender_id).scalar() is not None


class UserSession:

    def __init__(self, object_class, *args, **kwargs):
        self.objClass = object_class
        self.update(*args, **kwargs)

    def __getitem__(self, sender_id):
        try:
            db_session.session.query(Sender).filter(Sender.sender_id == sender_id).one()
        except NoResultFound:
            raise KeyError(sender_id)
        return self.objClass(sender_id)

    def __setitem__(self, sender_id, val):
        try:
            sender = db_session.session.query(Sender).filter(Sender.sender_id == sender_id).one()
        except NoResultFound:
            sender = Sender(sender_id=sender_id)
            db_session.session.add(sender)
            db_session.session.commit()
        self.objClass(sender.sender_id, val)

    def update(self, *args, **kwargs):
        for k, v in dict(*args, **kwargs).items():
            self[k] = v

    def __delitem__(self, sender_id):
        try:
            db_session.session.query(Sender).filter(Sender.sender_id == sender_id).one().delete()
            db_session.session.commit()
        except NoResultFound:
            raise KeyError(sender_id)

    def __contains__(self, sender_id):
        return db_session.session.query(Sender).filter(
            Sender.sender_id == sender_id).scalar() is not None


class Chat(ChatBot):

    def __init__(self, *arg, **kwargs):
        db_session.session = Session()
        super(Chat, self).__init__(*arg, **kwargs)
        self._memory = UserSession(UserMemory, self._memory)
        self._conversation = UserSession(UserConversation, self._conversation)
        self._topic.topic = UserTopic(self._topic.topic)
        db_session.session.close()

    @property
    def conversation(self):
        return self._conversation

    @property
    def memory(self):
        return self._memory

    @property
    def topic(self):
        return self._topic

    @property
    def attr(self):
        return self._attr

    def respond(self, message, session_id):
        self._attr[session_id] = {
            'match': None,
            'pmatch': None,
            '_quote': False,
            'substitute': True
        }
        self._conversation[session_id].append_user_message(message)
        response = super().respond(message.rstrip(".! \n\t"),
                                   session_id=session_id)
        self._conversation[session_id].append_bot_message(response)
        del self._attr[session_id]
        return response

    def start_new_session(self, session_id, topic=""):
        super().start_new_session(session_id)
        start_message = getattr(settings, "START_MESSAGE", "Welcome to ChatBotAI")
        self._conversation[session_id].append_bot_message(start_message)
        return start_message

    def has_session(self, session_id):
        return db_session.session.query(Sender).filter(
            Sender.sender_id == session_id).scalar() is not None

