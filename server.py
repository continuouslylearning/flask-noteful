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
        "name": self.title,
        "content": self.content
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


# Note endpoints
@app.route('/api/notes', methods=['GET'])
def get_notes():
  notes = session.query(Notes).all()
  notes = [note.as_dictionary() for note in notes]
  return jsonify(notes)


@app.route('/api/notes', methods=['POST'])
@accept("application/json")
def post_note():
  data = request.json
  note = Notes(title=data['title'], content=data['content'])
  session.add(note)
  session.commit()
  return ''

# folder endpoints

@app.route('/api/folders', methods=['GET'])
def get_folders():
  folders = session.query(Folders).all()
  folders = [folder.as_dictionary() for folder in folders]
  return jsonify(folders)

@app.route('/api/folders', methods=['POST'])
@accept("application/json")
def post_folder():
  data = request.json
  folder = Folders(name=data['name'])
  try:
    session.add(folder)
    session.commit()
  except IntegrityError:
    return Response(json.dumps({'message': 'Folder name already exists'}), 400, mimetype='application/json')
  return Response(folder.as_dictionary, 201, mimetype='application/json')

if __name__ == "__main__":
  app.run()