import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy

# Инициализируем Flask с использованием каталога instance
app = Flask(__name__, instance_relative_config=True)

# Создаем каталог instance, если его еще нет
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

# Настроим подключение к базе данных (SQLite)
db_path = os.path.join(app.instance_path, 'survey.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ----------------------------
# Модели для опроса
# ----------------------------

class Survey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    questions = db.relationship('Question', backref='survey', cascade="all, delete", lazy=True)
    responses = db.relationship('SurveyResponse', backref='survey', cascade="all, delete", lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    allow_comments = db.Column(db.Boolean, default=False)
    multiple_selection = db.Column(db.Boolean, default=False)
    survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'), nullable=False)
    options = db.relationship('Option', backref='question', cascade="all, delete", lazy=True)

class Option(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(300), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)

# ----------------------------
# Модели для прохождения опроса
# ----------------------------

class SurveyResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    answers = db.relationship('Answer', backref='survey_response', cascade="all, delete", lazy=True)

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    survey_response_id = db.Column(db.Integer, db.ForeignKey('survey_response.id'), nullable=False)
    # Храним выбранные варианты как строку (например, "1,3") – для простоты демонстрации
    selected_options = db.Column(db.String(500), nullable=True)
    comment = db.Column(db.Text, nullable=True)

# ----------------------------
# Маршруты приложения
# ----------------------------

# Главная страница — список опросов (с кнопками для редактирования, удаления и ссылки на прохождение)
@app.route('/')
def index():
    surveys = Survey.query.all()
    return render_template('index.html', surveys=surveys)

# Страница создания нового опроса
@app.route('/survey/new', methods=['GET', 'POST'])
def create_survey():
    if request.method == 'POST':
        title = request.form.get("title")
        survey = Survey(title=title)
        db.session.add(survey)
        
        # Обрабатываем вопросы: поля формы именуются как questions[индекс][...]
        i = 0
        while f"questions[{i}][text]" in request.form:
            q_text = request.form.get(f"questions[{i}][text]")
            allow_comments = True if request.form.get(f"questions[{i}][allow_comments]") else False
            multiple_selection = True if request.form.get(f"questions[{i}][multiple_selection]") else False
            options = request.form.getlist(f"questions[{i}][options][]")
            
            question = Question(
                text=q_text,
                allow_comments=allow_comments,
                multiple_selection=multiple_selection,
                survey=survey
            )
            db.session.add(question)
            for opt_text in options:
                if opt_text.strip() != "":
                    option = Option(text=opt_text, question=question)
                    db.session.add(option)
            i += 1
        
        db.session.commit()
        # После создания опроса можно вывести ссылку для его прохождения
        # Например: http://<IP>:5000/survey/ID/take
        return redirect(url_for('index'))
    
    return render_template('survey_editor.html')

# Новый маршрут для удаления опроса (как было показано ранее)
@app.route('/survey/delete/<int:survey_id>', methods=['POST'])
def delete_survey(survey_id):
    survey = Survey.query.get_or_404(survey_id)
    db.session.delete(survey)
    db.session.commit()
    return redirect(url_for('index'))

# Новый маршрут для прохождения опроса
@app.route('/survey/<int:survey_id>/take', methods=['GET', 'POST'])
def take_survey(survey_id):
    survey = Survey.query.get_or_404(survey_id)
    if request.method == 'POST':
        response = SurveyResponse(survey_id=survey.id)
        db.session.add(response)
        # Для каждого вопроса собираем выбранные варианты и комментарий (если есть)
        for question in survey.questions:
            key = f'question_{question.id}_options'
            selected_options = []
            if question.multiple_selection:
                # Для флажков — получаем список значений
                selected_options = request.form.getlist(key)
            else:
                # Для радио-кнопок получаем единственное значение
                option = request.form.get(key)
                if option:
                    selected_options = [option]
            comment = request.form.get(f'question_{question.id}_comment')
            answer = Answer(
                question_id=question.id,
                survey_response=response,
                selected_options=",".join(selected_options) if selected_options else None,
                comment=comment if comment else None
            )
            db.session.add(answer)
        db.session.commit()
        return redirect(url_for('thank_you'))
    return render_template('survey_take.html', survey=survey)

# Страница благодарности после завершения опроса
@app.route('/thank-you')
def thank_you():
    return "<h1>Спасибо за участие в опросе!</h1>"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Запуск приложения, чтобы оно слушало все сетевые интерфейсы (доступно из локальной сети)
    app.run(debug=True, host='0.0.0.0', port=5000)
