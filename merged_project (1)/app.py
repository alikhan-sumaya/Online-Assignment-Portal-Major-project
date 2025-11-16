from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from utils.plagiarism_checker import compare_file_against_folder
 
from flask import send_from_directory

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['MAIL_DEBUG'] = True


if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)
from flask_mail import Mail, Message

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Replace with your email provider's SMTP server
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'TeacherOne.1234@gmail.com'  # Replace with your email address
app.config['MAIL_PASSWORD'] = 'mnio tmlp mokm anew'  # Replace with your email password Teacher@1234
app.config['MAIL_DEFAULT_SENDER'] = 'TeacherOne.1234@gmail.com'

mail = Mail(app)





import os
from werkzeug.utils import secure_filename

# Configuration for file uploads
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}
 

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # "student" or "teacher"

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    question_file_path = db.Column(db.String(200), nullable=True)  # Path to question file



class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    marks = db.Column(db.Integer, nullable=True)  # Store marks instead of grades
    similarity = db.Column(db.Float, nullable=True)  # similarity percentage (0-100)


# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        new_user = User(username=username, email=email, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully!')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['user_id'] = user.id
            session['role'] = user.role
            flash('Logged in successfully!')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials!')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] == 'student':
        return redirect(url_for('student_dashboard'))
    elif session['role'] == 'teacher':
        return redirect(url_for('teacher_dashboard'))
    return redirect(url_for('login'))

 

@app.route('/student')
def student_dashboard():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    assignments = Assignment.query.all()
    submissions = Submission.query.filter_by(student_id=session['user_id']).all()

    # Create a mapping of assignment IDs to submissions
    submission_map = {sub.assignment_id: sub for sub in submissions}

    # Debug: Print submission map to console for verification
    print("Submission Map:", submission_map)

    return render_template(
        'student.html',
        assignments=assignments,
        submissions=submission_map
    )



@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    if session.get('role') != 'teacher':
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Handle assignment creation
        title = request.form['title']
        description = request.form['description']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        question_file = request.files['question_file']

        question_file_path = None
        if question_file and allowed_file(question_file.filename):
            filename = secure_filename(question_file.filename)
            question_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            question_file.save(question_file_path)

        # Convert dates to datetime objects
        start_time_dt = datetime.strptime(start_time, '%Y-%m-%d')
        end_time_dt = datetime.strptime(end_time, '%Y-%m-%d')

        # Add assignment to the database
        new_assignment = Assignment(
            title=title,
            description=description,
            start_time=start_time_dt,
            end_time=end_time_dt,
            question_file_path=question_file_path
        )
        db.session.add(new_assignment)
        db.session.commit()

        # Send email notifications to all students
        send_email_notifications_to_students(title, description)

        flash('Assignment created successfully and notifications sent!', 'success')
        return redirect(url_for('teacher_dashboard'))

    # Fetch all assignments for the teacher
    assignments = Assignment.query.all()

    return render_template('teacher.html', assignments=assignments)


@app.route('/upload/<int:assignment_id>', methods=['GET', 'POST'])
def upload(assignment_id):
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    if request.method == 'POST':
        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            new_submission = Submission(assignment_id=assignment_id, student_id=session['user_id'], file_path=file_path)
            db.session.add(new_submission)

            # --- Run plagiarism check against existing uploads ---
            try:
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                max_sim, details = compare_file_against_folder(file_path, app.config['UPLOAD_FOLDER'])
                new_submission.similarity = max_sim
            except Exception as e:
                print('Plagiarism check error:', e)
            db.session.commit()
            flash('Assignment submitted successfully!')
            return redirect(url_for('student_dashboard'))
    return render_template('upload.html', assignment_id=assignment_id)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files from the uploads folder."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/evaluate/<int:assignment_id>', methods=['GET', 'POST'])
def evaluate_submissions(assignment_id):
    """Evaluate submissions for a specific assignment."""
    if session.get('role') != 'teacher':
        return redirect(url_for('login'))

    # Fetch the assignment
    assignment = Assignment.query.get(assignment_id)
    if not assignment:
        flash("Assignment not found!", "danger")
        return redirect(url_for('teacher_dashboard'))

    # Fetch submissions for this assignment
    submissions = Submission.query.filter_by(assignment_id=assignment_id).all()

    if request.method == 'POST':
        for submission in submissions:
            # Extract marks input for the current submission
            marks_key = f"marks_{submission.id}"
            if marks_key in request.form:
                marks = request.form[marks_key]

                # Update marks if valid
                if marks.strip().isdigit():
                    submission.marks = int(marks.strip())
                    db.session.commit()

        flash('Marks submitted successfully!', 'success')
        return redirect(url_for('evaluate_submissions', assignment_id=assignment_id))

    return render_template('evaluate.html', assignment=assignment, submissions=submissions)


@app.route('/test-email')
def test_email():
    try:
        msg = Message('Test Email', recipients=['alikhansumaya090@gmail.com'])
        msg.body = 'This is a test email from Flask-Mail.'
        mail.send(msg)
        return "Email sent successfully!"
    except Exception as e:
        return f"Error: {e}"


import os
from werkzeug.utils import secure_filename

# Allowed file extensions for question uploads
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/create_assignment', methods=['GET', 'POST'])
def create_assignment():
    if session.get('role') != 'teacher':
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        start_time = request.form['start_time']
        end_time = request.form['end_time']

        question_file = request.files['question_file']
        question_file_path = None

        if question_file and allowed_file(question_file.filename):
            filename = secure_filename(question_file.filename)
            question_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            question_file.save(question_file_path)

        new_assignment = Assignment(
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            question_file_path=question_file_path
        )
        db.session.add(new_assignment)
        db.session.commit()

        flash('Assignment created successfully!', 'success')
        return redirect(url_for('teacher_dashboard'))

    return render_template('create_assignment.html')



@app.route('/delete_submission/<int:submission_id>', methods=['POST'])
def delete_submission(submission_id):
    """Delete a student's uploaded submission."""
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    submission = Submission.query.get(submission_id)
    if submission and submission.student_id == session['user_id']:
        # Delete the file from the server
        if os.path.exists(submission.file_path):
            os.remove(submission.file_path)
        # Delete the submission record from the database
        db.session.delete(submission)
        db.session.commit()
        flash('Submission deleted successfully!', 'success')
    else:
        flash('Unauthorized action or submission not found!', 'danger')

    return redirect(url_for('student_dashboard'))


@app.route('/reupload/<int:assignment_id>', methods=['GET', 'POST'])
def reupload(assignment_id):
    """Allow students to reupload an assignment."""
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    submission = Submission.query.filter_by(
        assignment_id=assignment_id, student_id=session['user_id']
    ).first()

    if request.method == 'POST':
        # Delete the old submission if it exists
        if submission:
            if os.path.exists(submission.file_path):
                os.remove(submission.file_path)
            db.session.delete(submission)

        # Save the new file
        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            new_submission = Submission(
                assignment_id=assignment_id,
                student_id=session['user_id'],
                file_path=file_path,
            )
            db.session.add(new_submission)
            db.session.commit()
            flash('Assignment reuploaded successfully!', 'success')
            return redirect(url_for('student_dashboard'))

    return render_template('upload.html', assignment_id=assignment_id)


       
def send_email_notifications_to_students(title, description):
    students = User.query.filter_by(role='student').all()  # Fetch all students from the database
    student_emails = [student.email for student in students]

    if not student_emails:
        print("No students to notify.")
        return  # No students to notify

    subject = f"New Assignment: {title}"
    body = f"""Hello Students,

A new assignment has been created:

Title: {title}
Description: {description}

Please check your dashboard for more details.

Best regards,
Your Teacher
"""

    try:
        with mail.connect() as conn:
            for email in student_emails:
                print(f"Sending email to: {email}")  # Debug statement
                message = Message(subject, recipients=[email], body=body)
                conn.send(message)
        print("Emails sent successfully.")
    except Exception as e:
        print(f"Error sending email: {e}")



@app.route('/check_similarity/<int:submission_id>', methods=['POST'])
def check_similarity(submission_id):
    if session.get('role') != 'teacher':
        return redirect(url_for('login'))
    submission = Submission.query.get(submission_id)
    if not submission:
        flash("Submission not found.", "danger")
        
    # If AJAX request, return JSON with new similarity
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return json.dumps({'success': True, 'similarity': submission.similarity}), 200, {'Content-Type': 'application/json'}
    return redirect(request.referrer or url_for('teacher_dashboard'))
    try:
        max_sim, details = compare_file_against_folder(submission.file_path, app.config['UPLOAD_FOLDER'])
        submission.similarity = max_sim
        db.session.commit()
        flash(f"Similarity updated: {max_sim}%", "success")
    except Exception as e:
        flash(f"Error running similarity check: {e}", "danger")
    return redirect(request.referrer or url_for('teacher_dashboard'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
