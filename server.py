from flask import Flask, jsonify, request, Response, json
from functools import wraps
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.exc import IntegrityError

engine = create_engine('postgres://wctgxite:AoufCZFn17xivpL74SSpfxCEoDdPgB2h@pellefant.db.elephantsql.com:5432/wctgxite')
Session = sessionmaker(bind=engine)
session = Session()
Base = declarative_base()

# models
class Folders(Base):
  __tablename__ = 'folders'
  
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

  id = Column(Integer, primary_key=True)
  title = Column(String, nullable=False)
  content = Column(String, nullable=True)
  folder_id = Column(Integer, ForeignKey(Folders.id), nullable=True)

  def as_dictionary(self):
    folder = {
        "id": self.id,
        "title": self.title,
        "content": self.content,
        "folder_id": self.folder_id
    }
    return folder


Base.metadata.create_all(engine)

app = Flask(__name__)

# decorators
def accept(mimetype):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if mimetype in request.accept_mimetypes:
                return func(*args, **kwargs)
            message = "Request must accept {} data".format(mimetype)
            data = json.dumps({"message": message})
            return Response(data, 406, mimetype="application/json")
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
def post_note():

  data = request.json

  title = data.get('title')
  folder_id = data.get('folder_id')
  content = data.get('content')

  if not title:
    return jsonify({'message': 'Note name is required'}), 400

  # in keyword checks if folder_id key is in data dictionary
  # folder_id is optional, does not return 400 if folder_id key is missing
  if 'folder_id' in data:
    folder = session.query(Folders).filter(Folders.id==folder_id).first()
    if not folder:
      return jsonify({ 'message': 'Folder id is not valid'}), 400

  note = Notes(title=title, content=content, folder_id=folder_id)
  session.add(note)
  session.commit()
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
    ## sqlalchemy raises an IntegrityError for duplicate values
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

if __name__ == "__main__":
  app.run()