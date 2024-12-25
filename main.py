from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from groq import Groq
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.abspath("vector.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
client = Groq(api_key='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')
vectorizer = TfidfVectorizer()

# Models
class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    subtopics = db.relationship('Subtopic', backref='topic', lazy=True, cascade="all, delete-orphan")
    attachments = db.relationship('Attachment', backref='topic', lazy=True, cascade="all, delete-orphan")

class Subtopic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    role_ids = db.Column(db.PickleType, nullable=False)  # Storing as a list
    attachments = db.relationship('Attachment', backref='subtopic', lazy=True, cascade="all, delete-orphan")

class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=True)
    sub_topic_id = db.Column(db.Integer, db.ForeignKey('subtopic.id'), nullable=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)


def data():
    # Path to the SQLite database
    db_path = os.path.abspath("vector.db")

    # Create a connection to the SQLite database
    engine = create_engine(f"sqlite:///{db_path}")

    # Create a session
    Session = sessionmaker(bind=engine)
    session = Session()

    # Raw SQL query to fetch all subtopics' content
    sql_query = text("SELECT content FROM subtopic")

    # Execute the query
    result = session.execute(sql_query)

    # Fetch all results and extract the 'content' field using index access
    content_list = [row[0] for row in result]  # Accessing the first element of the tuple
    
    return content_list

def foo(query, top_k=3):
    query = promt(f"Question: {query} rephrase without loosing any information, find necessary informational and than than than send it to RAG ")
    document_text = data()
    print(query)
    print("------------------------------------\n")
    tfidf_matrix = vectorizer.fit_transform([query] + document_text)
    query_vector = tfidf_matrix[0]
    text_vectors = tfidf_matrix[1:]
    similarities = cosine_similarity(query_vector, text_vectors).flatten()

    top_k_indices = similarities.argsort()[-top_k:][::-1]
    top_matches = [(document_text[i], similarities[i]) for i in top_k_indices]

    result = f"Question: {query}\n\nTop {top_k} Matches:\n"
    for idx, (doc, score) in enumerate(top_matches):
        result += f"\n{idx + 1}. Score: {score:.2f}\n{doc}\n"
    print(result)
    print('------------------------------------------------------------------------')

    return result


def promt(text):
    completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {
                "role": "user",
                "content": f"{text}"
            }
        ],
        temperature=1,
        max_tokens=1024,
        top_p=1,
        stream=True,
        stop=None,
    )
    k = ''
    for chunk in completion:
        if type((chunk.choices[0].delta.content)) is str:
            k += (chunk.choices[0].delta.content)
        

    return k

@app.route("/get")
def get_bot_response():
    print('get')
    message = request.args.get('msg')
    text = foo(message)
    print(message)
    result = promt(text)
    return result


@app.route('/')
def home():
    return render_template('home.html')

@app.route('/create_topic')
def create_topic():
    return render_template('create_topic.html')

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/create_topic', methods=['POST'])
def add_topic():
    print('ok')
    data = request.get_json()
    print('ok1')
    # Create Topic
    print(data)
    topic = Topic(id=data['id'], title=data['title'], description=data['description'])
    db.session.add(topic)

    # Create Subtopics
    for subtopic_data in data.get('subtopics', []):
        subtopic = Subtopic(
            id=subtopic_data['id'],
            title=subtopic_data['title'],
            content=subtopic_data['content'],
            topic_id=subtopic_data['topicId'],
            role_ids=subtopic_data['roleIds']
        )
        topic.subtopics.append(subtopic)

        # Add Subtopic Attachments
        for attachment_data in subtopic_data.get('attachments', []):
            attachment = Attachment(
                id=attachment_data['id'],
                topic_id=attachment_data['topicId'],
                sub_topic_id=attachment_data['subTopicId'],
                file_name=attachment_data['fileName'],
                file_type=attachment_data['fileType']
            )
            subtopic.attachments.append(attachment)

    # Add Topic Attachments
    for attachment_data in data.get('attachments', []):
        attachment = Attachment(
            id=attachment_data['id'],
            topic_id=attachment_data['topicId'],
            sub_topic_id=attachment_data['subTopicId'],
            file_name=attachment_data['fileName'],
            file_type=attachment_data['fileType']
        )
        topic.attachments.append(attachment)

    db.session.commit()
    return jsonify({'message': 'Topic added successfully!'})

@app.route('/print_database', methods=['GET'])
def print_database():
    result = {
        "topics": [],
        "subtopics": [],
        "attachments": []
    }

    # Query Topics
    topics = Topic.query.all()
    for topic in topics:
        result["topics"].append({
            "id": topic.id,
            "title": topic.title,
            "description": topic.description
        })

    # Query Subtopics
    subtopics = Subtopic.query.all()
    for subtopic in subtopics:
        result["subtopics"].append({
            "id": subtopic.id,
            "title": subtopic.title,
            "content": subtopic.content,
            "topic_id": subtopic.topic_id,
            "role_ids": subtopic.role_ids
        })

    # Query Attachments
    attachments = Attachment.query.all()
    for attachment in attachments:
        result["attachments"].append({
            "id": attachment.id,
            "topic_id": attachment.topic_id,
            "sub_topic_id": attachment.sub_topic_id,
            "file_name": attachment.file_name,
            "file_type": attachment.file_type
        })

    # Return JSON response
    return jsonify(result)

@app.route('/edit', methods=['POST'])
def edit():
    try:
        data = request.get_json()
        if not data or 'subtopics' not in data:
            return jsonify({'error': 'Invalid input: Missing subtopics data'}), 400
        for subtopic_data in data['subtopics']:
            if 'id' not in subtopic_data or 'title' not in subtopic_data or 'content' not in subtopic_data:
                return jsonify({'error': 'Invalid input: Subtopic requires id, title, and content'}), 400
            subtopic = Subtopic.query.get(subtopic_data['id'])
            if not subtopic:
                return jsonify({'error': f'Subtopic with ID {subtopic_data["id"]} not found'}), 404
            subtopic.title = subtopic_data['title']
            subtopic.content = subtopic_data['content']
            subtopic.role_ids = subtopic_data.get('roleIds', subtopic.role_ids)

            existing_attachment_ids = {attachment.id for attachment in subtopic.attachments}
            new_attachments = subtopic_data.get('attachments', [])

            for attachment_data in new_attachments:
                if 'id' not in attachment_data or 'fileName' not in attachment_data or 'fileType' not in attachment_data:
                    return jsonify({'error': 'Invalid input: Attachment requires id, fileName, and fileType'}), 400

                if attachment_data['id'] in existing_attachment_ids:
                    attachment = Attachment.query.get(attachment_data['id'])
                    attachment.file_name = attachment_data['fileName']
                    attachment.file_type = attachment_data['fileType']
                else:
                    new_attachment = Attachment(
                        id=attachment_data['id'],
                        topic_id=attachment_data.get('topicId', subtopic.topic_id),
                        sub_topic_id=subtopic.id,
                        file_name=attachment_data['fileName'],
                        file_type=attachment_data['fileType']
                    )
                    subtopic.attachments.append(new_attachment)

        db.session.commit()
        return jsonify({'message': 'Subtopics and attachments updated successfully'}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@app.route('/delete', methods=['DELETE'])
def Delete():
    return jsonify({'message': 'Topic deleted successfully!'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0')
