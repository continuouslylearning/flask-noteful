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
  notes = [note.as_dictionary() for note in notes]
  return jsonify(notes)


@app.route('/api/notes', methods=['POST'])
@accept("application/json")
def post_note():
  data = request.json
  title = data['title']

  # use dictionary's get method instead of using brackets to search for key
  # get method returns None if key does not exist, brackets syntax raises KeyError if key does not exist
  folder_id = data.get('folder_id')

  if not title:
    return jsonify({'message': 'Note name is required'}), 400

  if 'folder_id' in data:
    folder = session.query(Folders).filter(Folders.id==folder_id).first()
    if not folder:
      return jsonify({ 'message': 'Folder id is not valid'}), 400

  note = Notes(title=title, content=data['content'], folder_id=folder_id)
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


# <id> is the dynamic path segment for folder id
# integer type set for id path argument 
# returns 404 when a string value provided
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