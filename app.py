from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import pymysql
import pymysql.cursors
import random
import string
from functools import wraps
import bcrypt
import logging
import datetime

import os

app = Flask(__name__)
app.secret_key = b'\x00\xdc8\xfa\xb1\xd7\x06\x96\x02\xdb<F@7\xf0\xf3\xbf$\x8cb\x94w\xe8\xa3'

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


def generate_random_alphanumeric(length):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))


def seconds_to_hms(seconds):
    return str(datetime.timedelta(seconds=seconds))


def hash_password(password):
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt)
    return hashed_password.decode('utf-8')


def check_password(stored_password, provided_password):
    stored_password_bytes = stored_password.encode('utf-8')
    provided_password_bytes = provided_password.encode('utf-8')
    return bcrypt.checkpw(provided_password_bytes, stored_password_bytes)


def get_db_connection():
    try:
        return pymysql.connect(host='localhost', user='root', password='', database='vbls',
                               cursorclass=pymysql.cursors.DictCursor)
    except pymysql.MySQLError as e:
        print(f"The error '{e}' occurred")
        return None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    connection = get_db_connection()
    if connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, password FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()
                if user and check_password(user['password'], password):
                    session['user_id'] = user['id']
                    return redirect(url_for('video_learning'))
            flash('Invalid credentials. Please try again.', 'error')
        finally:
            connection.close()
    else:
        flash('Database connection failed.', 'error')
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))


def get_comments():
    connection = get_db_connection()
    comments = []
    if connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT comment_id, content, qa_type, start_time, end_time FROM video_comments ORDER BY id DESC LIMIT 10")
                comments = cursor.fetchall()  # Fetches all rows from the last executed statement
        except pymysql.MySQLError as e:
            print(f"The error '{e}' occurred")
        finally:
            connection.close()
    return comments


def get_threads(discussion_id):
    connection = get_db_connection()
    threads = []

    if not connection:
        os.abort(500, description="Database connection failed.")

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                       SELECT D.d_content, D.d_id, C.comment_id, C.content, C.qa_type
                       FROM discussions D
                       JOIN video_comments C ON D.c_id = C.comment_id
                       WHERE D.c_id = %s
                   """, (discussion_id,))
            threads = cursor.fetchall()  # Changed to fetchall() to potentially get multiple comments
            # print(threads)
            if not threads:
                os.abort(404, description="Record not found.")
    except pymysql.MySQLError as e:
        print(f"The error '{e}' occurred")  # Consider switching to logging
        os.abort(500, description="Failed to fetch records.")
    finally:
        connection.close()

    return threads


def get_comment_byID(discussion_id):
    connection = get_db_connection()
    threads = []

    if not connection:
        os.abort(500, description="Database connection failed.")

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                       SELECT * FROM video_comments C
                       WHERE C.comment_id = %s
                   """, (discussion_id,))
            threads = cursor.fetchall()  # Changed to fetchall() to potentially get multiple comments
            # print(threads)
            if not threads:
                os.abort(404, description="Record not found.")
    except pymysql.MySQLError as e:
        print(f"The error '{e}' occurred")  # Consider switching to logging
        os.abort(500, description="Failed to fetch records.")
    finally:
        connection.close()

    return threads


@app.route('/filter_comments', methods=['GET'])
def filter_comments():
    comments = get_comments()
    comment_type = request.args.get('type')  # Get the type from query parameters

    if comment_type == 'all':
        return jsonify(comments)
    else:
        try:
            # Convert comment_type to integer and filter comments
            comment_type_int = int(comment_type)
            filtered_comments = [comment for comment in get_comments() if comment['qa_type'] == comment_type_int]
            return jsonify(filtered_comments)
        except ValueError:
            # Handle the case where conversion fails
            return "Invalid input type. Please provide a numeric type.", 400


@app.route('/add_comment', methods=['POST'])
def add_comment():
    comment_content = request.form['comment']
    start_time = request.form.get('startTime', type=int)
    end_time = request.form.get('endTime', type=int)
    random_string = generate_random_alphanumeric(10)

    # Perform toxic classification
    toxic_type = 0
    # Perform Question and Answer Classification
    qa_type = 0

    connection = get_db_connection()
    if connection:
        try:
            with connection.cursor() as cursor:
                sql = "INSERT INTO video_comments (comment_id, content, qa_type, toxic_type, start_time, end_time) " \
                      "VALUES (%s, %s, %s, %s, %s, %s)"
                cursor.execute(sql, (random_string, comment_content, qa_type, toxic_type, start_time, end_time))
                connection.commit()
            return jsonify({'message': 'Comment added successfully'}), 200
        except Exception as e:
            connection.rollback()
            logging.error(f"Failed to add comment: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            connection.close()
    else:
        logging.error("Database connection failed")
        return jsonify({'error': 'Database connection failed'}), 500


@app.route('/add_reply', methods=['POST'])
def add_reply():
    comment_content = request.form['comment']
    commentID  = request.form['commentID']
    random_string = generate_random_alphanumeric(10)

    # Perform Question and Answer Classification
    d_qa_type = 0

    connection = get_db_connection()
    if connection:
        try:
            with connection.cursor() as cursor:
                sql = "INSERT INTO discussions (c_id, d_id, d_content, d_qa_type) " \
                      "VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, (commentID, random_string, comment_content, d_qa_type))
                connection.commit()
            return jsonify({'message': 'Reply added successfully'}), 200
        except Exception as e:
            connection.rollback()
            logging.error(f"Failed to add reply: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            connection.close()
    else:
        logging.error("Database connection failed")
        return jsonify({'error': 'Database connection failed'}), 500


@app.route('/video_learning')
@login_required
def video_learning():
    comments = get_comments()
    for comment in comments:
        comment['formatted_start_time'] = seconds_to_hms(comment['start_time'])
        comment['formatted_end_time'] = seconds_to_hms(comment['end_time'])
    return render_template('video_learning.html', comments=comments)


@app.route('/discussion')
@login_required
def discussion():
    discussion_id = request.args.get('id')
    threads = get_threads(discussion_id)
    original_comment = get_comment_byID(discussion_id)

    for comment in original_comment:
        comment['formatted_start_time'] = seconds_to_hms(comment['start_time'])
        comment['formatted_end_time'] = seconds_to_hms(comment['end_time'])

    return render_template('discussion.html', threads=threads, original_comment=original_comment, discussion_id=discussion_id)


if __name__ == '__main__':
    app.run(debug=True)
