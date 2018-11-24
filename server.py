from flask import Flask, jsonify, request, Response, json
from functools import wraps
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import BYTEA
import os
import jwt
import bcrypt

# Flask app instance
app = Flask(__name__, static_url_path='')

# read URI for postgres database from  'DBI_URI' environment variable
DB_URI = os.environ.get("DB_URI", default=None)
JWT_SECRET = os.environ.get("JWT_SECRET", default=None)

# set up for sqlalchemy session
engine = create_engine(DB_URI)
Session = sessionmaker(bind=engine)
session = Session()
Base = declarative_base()

# models
class Folders(Base):
  __tablename__ = 'folders'
  
  # defines schema for folders table
  id = Column(Integer, primary_key=True)
  name = Column(String, unique=True)
  notes = relationship('Notes', uselist=True)

  # converts folder instance into a dictionary
  def as_dictionary(self):
      folder = {
          "id": self.id,
          "name": self.name
      }
      return folder


class Notes(Base):
  __tablename__ = 'notes'

  # folder id is set as a foreign key in the notes table
  # by default, when a folder is deleted, folder id in related notes are set to null 
  id = Column(Integer, primary_key=True)
  title = Column(String, nullable=False)
  content = Column(String, nullable=True)
  folder_id = Column(Integer, ForeignKey(Folders.id), nullable=True)
  # user_id = Column(Integer, ForeignKey(Users.id), nullable=False)
  # specify delete on cascade constraint for records in 'note_tags' table
  # when note is deleted, referencing records in note_tags are deleted
  note_tags = relationship('Note_tags', cascade='delete')

  def as_dictionary(self):
    note = {
        "id": self.id,
        "title": self.title,
        "content": self.content,
        "folder_id": self.folder_id,
        'tags': [tag.tag_id for tag in self.note_tags]
        # "user_id": self.user_id
    }
    return note

class Tags(Base):
  __tablename__ = 'tags'

  id = Column(Integer, primary_key=True)
  name = Column(String, nullable=False, unique=True)
  # delete on cascade constraint for note tags
  notes_tags = relationship('Note_tags', cascade='delete')

  def as_dictionary(self):
    tag = {
      "id": self.id,
      "name": self.name
    }
    return tag

# notes and tags cardinality is many-to-many so must create a 'note_tags' join table
class Note_tags(Base):
  __tablename__ = 'note_tags'

  # define a composite primary key consisting of two columns
  note_id = Column(Integer, ForeignKey(Notes.id), nullable=False, primary_key=True)
  tag_id = Column(Integer, ForeignKey(Tags.id), nullable=False, primary_key=True)

  def as_dictionary(self):
    note_tag = {
      'tag_id': self.tag_id
    }
    return note_tag

class Users(Base):
  __tablename__ = 'users'

  id = Column(Integer, nullable=False, primary_key=True)
  # unique constraint on username attribute
  # username and password are required fields but firstname and lastname are not
  username = Column(String, nullable=False, unique=True)
  password = Column(BYTEA, nullable=False)
  firstname = Column(String, nullable=True)
  lastname = Column(String, nullable=True)

  # declare a static method with @staticmethod decorator
  @staticmethod
  def hashpassword(password):
    # hash the given password with a salt factor of 10
    return bcrypt.hashpw(password.encode('utf8'), bcrypt.gensalt())

  def validatepassword(self,password):
    print(self.password)
    return bcrypt.checkpw(password.encode('utf8'), self.password)

  def as_dictionary(self):
    
    #make sure not to return the password in dictionary form
    user = {
      "id": self.id,
      "username": self.username,
      "firstname": self.firstname,
      "lastname": self.lastname
    }
    return user


Base.metadata.create_all(engine)

@app.route('/')
def root():
    return app.send_static_file('index.html')

# decorators
def accept(mimetype):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # if mimetype in request.accept_mimetypes:
            if request.content_type == mimetype:
                print(mimetype)
                print(request.accept_mimetypes)
                return func(*args, **kwargs)
            message = "Request must accept {} data".format(mimetype)
            data = json.dumps({"message": message})
            return Response(data, 406, mimetype="application/json")
        return wrapper
    return decorator

def jwt_auth():
  def decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
      # returns a new json web token when provided a valid token

      # look for auth token in authorization header
      bearer_token = request.headers.get('Authorization')

      if not bearer_token:
        return jsonify({'message': 'Authorization header is missing'}), 401

      # authorization header should conform to bearer scheme
      bearer_token = bearer_token.split(' ')
      scheme = bearer_token[0]
      token = bearer_token[1]

      # return 401 if request does not contain a proper bearer token
      if scheme != 'Bearer' or not token:
        return jsonify({'message': 'Bearer token is missing'}), 401

      # decodes the json web token
      # throws invalid signature error if the token signature is not valid
      try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
      except jwt.InvalidSignatureError:
        return jsonify({'message': 'Invalid auth token'}), 401

      # pass token payload to view function if authentication is successful
      return func(decoded, *args, **kwargs)
    return wrapper
  return decorator 


# Notes endpoints
@app.route('/api/notes', methods=['GET'])
def get_notes():
  notes = session.query(Notes).all()

  # list comprehension syntax
  # converts sql alchemy query results into a list of dictionaries
  notes = [note.as_dictionary() for note in notes]

  # jsonify converts the list of notes into a json string and returns a response with a json content-type
  return jsonify(notes)


# <id> is the dynamic path segment for note id
# integer type set for id path argument 
# returns 404 when a string value provided
@app.route('/api/notes/<int:id>', methods=['GET'])
def get_note(id):

  note = session.query(Notes).filter(Notes.id==id).first()

  if not note:
    return jsonify({'message': 'Note with this id does not exist'}), 404

  return jsonify(note.as_dictionary())


@app.route('/api/notes/<id>', methods=['PUT'])
@accept('application/json')
def update_note(id):
  
  # uses get method instead of using brackets syntax to search for keys in request.json dictionary
  # get method returns None if key does not exist, brackets syntax raises KeyError if key does not exist

  data = request.json

  title = data.get('title')
  folder_id = data.get('folder_id')
  content = data.get('content')

  # None and empty string are both falsey in Python
  # returns 400 if title key is missing or value of title key is an empty string
  if not title:
    return jsonify({'message': 'Note name is required'}), 400
  
  if 'folder_id' in data:
    folder = session.query(Folders).filter(Folders.id==folder_id).first()
    if not folder:
      return jsonify({ 'message': 'Folder id is not valid'}), 400

  updated_note = session.query(Notes).filter(Notes.id==id).first()

  if not updated_note:
    return jsonify({'message': 'Note with this id does not exist'}), 400

  updated_note.title = title
  updated_note.folder_id = folder_id
  updated_note.content = content 
  session.commit()

  return jsonify(updated_note.as_dictionary()), 201

@app.route('/api/notes', methods=['POST'])
@accept('application/json')
# @jwt_auth(payload)
def post_note():

  data = request.json

  title = data.get('title')
  folder_id = data.get('folder_id')
  content = data.get('content')
  tags = data.get('tags')

  if not title:
    return jsonify({'message': 'Note name is required'}), 400

  # in keyword checks if folder_id key is in data dictionary
  # folder_id is optional, does not return 400 if folder_id key is missing
  if 'folder_id' in data:
    folder = session.query(Folders).filter(Folders.id==folder_id).first()
    if not folder:
      return jsonify({ 'message': 'Folder id is not valid'}), 400

  # call flush before adding note_tags to session to make note id available
  note = Notes(title=title, content=content, folder_id=folder_id)
  session.add(note)
  session.flush()

  # add note_tags to session
  # calling commit persists the transaction into the database
  try: 
    for tag in tags:
      new_tag = Note_tags(note_id=note.id, tag_id=tag)
      session.add(new_tag)
    session.commit()
  except IntegrityError:
    # integrity error if thrown if a tag id is invalid
    # call rollback to reset current transaction
    session.rollback()
    return jsonify({'message': 'Invalid tag id'}), 400 
  print([tag.as_dictionary() for tag in note.note_tags])
  return jsonify(note.as_dictionary()), 201


@app.route('/api/notes/<int:id>', methods=['DELETE'])
def delete_note(id):
 
  note = session.query(Notes).filter(Notes.id==id).first()

  if not note:
    return jsonify({'message': 'Note with this id does not exist'}), 404
  
  session.delete(note)
  session.commit()

  return '', 204


# Folders endpoints

@app.route('/api/folders', methods=['GET'])
def get_folders():
  folders = session.query(Folders).all()
  folders = [folder.as_dictionary() for folder in folders]
  return jsonify(folders)


@app.route('/api/folders/<int:id>', methods=['GET'])
def get_folder(id):
  folder = session.query(Folders).filter(Folders.id==id).first()

  if not folder:
    return jsonify({'message': 'Folder with this id does not exist'}), 404

  return jsonify(folder.as_dictionary())

@app.route('/api/folders/<int:id>', methods=['PUT'])
@accept('application/json')
def update_folder(id):

  name = request.json.get('name')

  # folder name is required, returns 400 if name key is missing or an empty string
  if not name:
    return jsonify({'message': 'Folder name is missing'}), 400
  
  updated_folder = session.query(Folders).filter(Folders.id==id).first()
  
  # updated_folder variable is None if a folder with given id is not found
  if not updated_folder:
    return jsonify({'message': 'Folder with this id does not exist'}), 400

  try: 
    updated_folder.name = name
    # commit attempts to push the changes to the database
    session.commit()

  except IntegrityError:
    # IntegrityError is thrown when sqlalchemy tries to insert a duplicate name
    # rollback discards the unflushed changes to the folder object in the session
    session.rollback()
    return jsonify({'message': 'Folder name already exists'}), 400

  return jsonify(updated_folder.as_dictionary()), 201

@app.route('/api/folders', methods=['POST'])
@accept("application/json")
def post_folder():
  data = request.json
  name = data['name']

  # empty strings are falsey in Python
  if not name:
    return jsonify({'message': 'Folder name is missing'}), 400

  folder = Folders(name=name)

  try:
    session.add(folder)
    session.commit()

  except IntegrityError:
    session.rollback()
    return jsonify({'message': 'Folder name already exists'}), 400

  return jsonify(folder.as_dictionary()), 201

@app.route('/api/folders/<int:id>', methods=['DELETE'])
@accept('application/json')
def delete_folder(id):
  #the id path argument is passed to this view function

  folder = session.query(Folders).filter(Folders.id==id).first()

  if not folder:
    return jsonify({'message': 'Folder does not exist'}), 404

  session.delete(folder)
  session.commit()
  return '', 204


# Tags endpoints

@app.route('/api/tags', methods=['GET'])
def get_tags():
  tags = session.query(Tags).all()
  tags = [tag.as_dictionary() for tag in tags]
  
  return jsonify(tags)

@app.route('/api/tags/<int:id>', methods=['GET'])
def get_tag(id):
  tag = session.query(Tags).filter(Tags.id==id).first()
  if not tag:
    return jsonify({'message': 'Tag with this id does not exist'}), 404

  return jsonify(tag.as_dictionary()), 200

@app.route('/api/tags/<int:id>', methods=['PUT'])
@accept('application/json')
def update_tag(id):
  name = request.json.get('name')
  if not name:
    return jsonify({'message': 'Tag name is required'}), 404
  
  tag = session.query(Tags).filter(Tags.id==id).first()
  if not tag:
    return jsonify({'message': 'Tag with this id does not exist'}), 404
  
  try:
    tag.name = name
    session.commit()
  except IntegrityError:
    session.rollback()
    return jsonify({'message': 'Tag name already exists'}), 400

  return jsonify(tag.as_dictionary()), 201

@app.route('/api/tags', methods=['POST'])
@accept('application/json')
def create_tag():
  name = request.json.get('name')

  if not name:
    return jsonify({'message': 'Tag name is requierd'}), 400
  
  tag = Tags(name=name)

  try:
    session.add(tag)
    session.commit()

  except IntegrityError:
    session.rollback()
    return jsonify({'message': 'Tag name already exists'}), 400
  
  return jsonify(tag.as_dictionary()), 201

@app.route('/api/tags/<int:id>', methods=['DELETE'])
def delete_tag(id):
  tag = session.query(Tags).filter(Tags.id==id).first()
  
  if not tag:
    return jsonify({'message': 'Tag with this id does not exist'}), 404
  
  session.delete(tag)
  session.commit()
  return '', 204


@app.route('/auth/login', methods=['POST'])
@accept('application/json')
def login():

  # this endpoint signs and returns a json web token when provided a valid username and password
  username = request.json.get('username')
  password = request.json.get('password')

  # searches for the user in the database
  user = session.query(Users).filter(Users.username==username).first()
  if not user:
    return jsonify({'message': 'Username is invalid'})

  # validates the given password with bcrypt
  is_valid = user.validatepassword(password)

  if not is_valid:
    return jsonify({'message': 'Password is incorrect'})
  
  # signs a new json web token 
  auth_token = jwt.encode({ 'user': user.as_dictionary()}, JWT_SECRET, algorithm='HS256' )

  return jsonify({'authToken': auth_token.decode('utf8')}), 201


# decorate refresh endpoint with jwt authentication function
@app.route('/auth/refresh', methods=['POST'])
@accept('application/json')
@jwt_auth()
def refresh(decoded):
  # sign and return new token
  auth_token = jwt.encode({ 'user': decoded.get('user') }, JWT_SECRET, algorithm='HS256' )
  return jsonify({'authToken': auth_token.decode('utf8')}), 201


@app.route('/api/users', methods=['POST'])
@accept('application/json')
def create_user():

  # this endpoint creates new user accounts

  username = request.json.get('username')
  password = request.json.get('password')
  firstname = request.json.get('firstname')
  lastname = request.json.get('lastname')

  user_dict = {
    'username': username,
    'password': password,
    'firstname': firstname,
    'lastname': lastname
  }

  # username and password are required fields
  if not username or not password:
    return jsonify({'message': 'Username or password is missing'}), 400
  
  # username and password must be strings
  if not isinstance(username, str) or not isinstance(password, str):
    return jsonify({'message': 'Username and password must be strings'}), 400

  # leading and trailing whitespace not allowed in username or password
  if username.strip() != username or password.strip() != password:
    return jsonify({'message': 'Username and password cannot start or end with whitespace'}), 400

  # set min and max number of characters for username and password
  sized_fields = {
    'username': {
      'min': 5
    },
    'password': {
      'min': 6,
      'max': 72
    }
  }

  too_small = None
  too_large = None
  min = None
  max = None


  # iterating through dictionary only iterates through keys
  # use items() method on the dictionary to interate through key value pairs
  for field, size in sized_fields.items():
    if 'min' in size and size.get('min') > len(user_dict[field]):
      too_small = field
      min = size.get('min')
      break

    if 'max' in size and size.get('max') < len(user_dict[field]):
      too_large = field
      max = size.get('max')
      break
  
  # 3.6 Python 'f-string' syntax
  # f-string syntax evaluates expressions inside curly braces
  if too_small or too_large:
    return jsonify({'message': f'{too_small or too_large} must be at {"least" if too_small else "most"} {min if too_small else max} characters long'}), 400

  # hash the password before pushing a new user into the database
  new_user = Users(username=username, password=Users.hashpassword(password), firstname=firstname, lastname=lastname)

  # search database for an existing user with the same username
  user = session.query(Users).filter(Users.username==username).first()

  if user:
    return jsonify({'message': 'Username already exists'}), 400
  
  session.add(new_user)
  session.commit()
  
  return jsonify(new_user.as_dictionary()), 201



if __name__ == "__main__":
  app.run()