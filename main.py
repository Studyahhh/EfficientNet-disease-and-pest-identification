from datetime import datetime

from flask import Flask, request, redirect, url_for, render_template, flash, session, g, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import os
from pypinyin import lazy_pinyin
from crop_classification.utils import generate_unique_filename
from server.classify import predict_top3_classes
from server.connect import get_db

app = Flask(__name__)
app.secret_key = '666666'  # Set your secret key here

# MySQL configuration
MYSQL_HOST = 'localhost'
MYSQL_USER = 'root'
MYSQL_PASSWORD = '123456'
MYSQL_DB = 'agriculture'

# Configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:3306/{MYSQL_DB}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)


# Define User model
class User(db.Model):
    __tablename__ = 'user'  # 指定数据库中的表名为 'user'

    id = db.Column(db.Integer, primary_key=True)  # 定义 id 列，类型为 Integer，设置为主键
    username = db.Column(db.String(80), unique=True, nullable=False)  # 定义 username 列，类型为 String，值必须唯一，不能为空
    password_hash = db.Column(db.String(128), nullable=False)  # 定义 password_hash 列，类型为 String，不能为空

    def set_password(self, password):
        """
        将用户密码哈希后存储到 password_hash 列中
        :param password: 用户的原始密码
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """
        检查用户输入的密码是否与存储的哈希密码匹配
        :param password: 用户输入的密码
        :return: 如果匹配返回 True，否则返回 False
        """
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        """
        定义模型的字符串表示，主要用于调试和测试
        :return: 返回用户对象的字符串表示
        """
        return f"User('{self.username}')"


class RecycledItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(130), nullable=False)
    description = db.Column(db.Text, nullable=True)
    phone = db.Column(db.Text, nullable=True)
    is_putaway = db.Column(db.Boolean, nullable=True)
    created_at = db.Column(db.DateTime, default=func.now(), nullable=False)
    image_url = db.Column(db.String(255))  # 添加此字段以存储图片路径
    item_name = db.Column(db.String(20))  # 添加此字段以存储图片路径


class Issue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    reply = db.Column(db.Text, nullable=False)
    phone = db.Column(db.Text, nullable=False)
    name = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=func.now(), nullable=False)
    reply_date = db.Column(db.DateTime, default=func.now(), nullable=False)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=func.now(), nullable=False)


@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # 从表单获取用户名和密码
        username = request.form['username']
        password = request.form['password']

        # 在数据库中查询用户名为输入用户名的用户记录
        user = User.query.filter_by(username=username).first()

        if user:
            print(f"Stored password hash: {user.password_hash}")  # 打印存储的密码哈希值，便于调试
            print(user.check_password(password))
        # 检查用户是否存在并且输入的密码与存储的哈希密码匹配
        if user and user.check_password(password):
            print('OK')  # 打印调试信息，表示密码匹配
            # 成功登录
            session['user_id'] = user.id  # 将用户ID存储在会话中
            print(f"User ID: {user.id}")  # 打印用户ID，便于调试
            flash('登录成功！', 'success')  # 显示成功消息
            # 返回一个 JSON 响应，告知前端提交成功
            return {'success': True}
            # return redirect(url_for('notifications'))  # 重定向到用户仪表盘页面
        else:
            print('NO')  # 打印调试信息，表示密码不匹配或用户不存在
            # flash('用户名或密码错误，请重试。', 'danger')  # 显示错误消息
            return {'success': False}

    return render_template('login.html')  # 渲染登录页面模板


@app.route('/register/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            return {'success': False}
        else:
            new_user = User(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()

            return {'success': True}

    # For GET requests, check for flash messages
    flash_message = request.args.get('flashMessage')
    flash_type = request.args.get('flashType')
    return render_template('register.html', flash_message=flash_message, flash_type=flash_type)


# ------------------------ #

@app.route('/notifications')
def notifications():
    # t 标题最大长度
    # n 内容最大长度
    notification = Notification.query.all()
    return render_template('notifications.html', notifications=notification, t=10, n=30)


@app.route('/notifications/add', methods=['GET', 'POST'])
def add_notification():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        new_notification = Notification(title=title, content=content)
        db.session.add(new_notification)
        db.session.commit()
        flash('通知已添加！', 'success')
        return {'success': True}
        # return redirect(url_for('notifications'))
    return render_template('add_notification.html')


@app.route('/notifications/edit/<int:id>', methods=['GET', 'POST'])
def edit_notification(id):
    notification = Notification.query.get_or_404(id)
    if request.method == 'POST':
        notification.title = request.form['title']
        notification.content = request.form['content']
        db.session.commit()
        return {'success': True}
    else:
        # return {'success': False}
        flash_message = request.args.get('flashMessage')
        flash_type = request.args.get('flashType')
        return render_template('edit_notification.html', notification=notification, flash_message=flash_message,
                               flash_type=flash_type)


@app.route('/notifications/delete/<int:id>', methods=['POST'])
def delete_notification(id):
    notification = Notification.query.get_or_404(id)
    db.session.delete(notification)
    db.session.commit()
    flash('通知已删除！', 'success')
    return redirect(url_for('notifications'))


# 管理员 回收物

@app.route('/recycled-items/')
def recycled_items():
    items = RecycledItem.query.all()
    return render_template('recycled_items.html', recycled_items=items)


@app.route('/edit_recycled_item/<int:id>', methods=['GET', 'POST'])
def edit_recycled_item(id):
    item = RecycledItem.query.get_or_404(id)  # 获取指定ID的记录，如果记录不存在则返回404

    if request.method == 'POST':
        # 获取表单数据
        name = request.form.get('name')
        description = request.form.get('description')
        is_putaway = request.form.get('is_putaway') == 'true'  # 将表单数据转换为布尔值

        # 更新记录
        item.name = name
        item.description = description
        item.is_putaway = is_putaway

        db.session.commit()  # 提交更改

        flash('内容更新成功!', 'success')  # 显示成功消息
        return {'success': True}

    return render_template('edit_recycled_item.html', item=item)


@app.route('/recycled-items/add/', methods=['GET', 'POST'])
def add_recycled_item():
    save_folder = 'static/html_crop/uploadImages/recycle_images'

    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        item_name = request.form['item_name']
        description = request.form['introduction']

        # 确保上传文件夹存在
        if not os.path.exists(save_folder):
            os.makedirs(save_folder)
        if 'file' not in request.files:
            return jsonify({'message': 'No file part'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'message': 'No selected file'}), 400

        if file:
            filename = secure_filename(''.join(lazy_pinyin(file.filename)))
            unique_filename = generate_unique_filename(filename)
            filepath = os.path.join(save_folder, unique_filename)
            file.save(filepath)
            print(filename)
            print('回收物添加成功')

        is_putaway = 0
        new_item = RecycledItem(name=name, phone=phone, description=description, item_name=item_name,
                                is_putaway=is_putaway, image_url=filepath)
        db.session.add(new_item)
        db.session.commit()
        flash('回收物已成功添加！', 'success')
        return redirect(url_for('productRecycle'))
    return render_template('productRecycle.html')


@app.route('/delete_recycled_item/<int:id>', methods=['POST'])
def delete_recycled_item(id):
    item = RecycledItem.query.get_or_404(id)  # 获取指定ID的记录，如果记录不存在则返回404

    db.session.delete(item)  # 从会话中删除记录
    db.session.commit()  # 提交更改

    flash('内容更新成功!', 'success')  # 显示成功消息
    return redirect(url_for('recycled_items'))  # 重定向到回收物品列表页面


# -----------------问题---------------
@app.route('/issues/')
def issues():
    issues = Issue.query.all()
    return render_template('issues.html', issues=issues, n=20)


@app.route('/govHelp/add_issues/', methods=['GET', 'POST'])
def add_issue():
    if request.method == 'POST':
        phone = request.form['phone']
        name = request.form['name']
        title = request.form['title']
        description = request.form['description']
        new_issue = Issue(phone=phone, name=name, title=title, description=description)
        db.session.add(new_issue)
        db.session.commit()
        flash('问题已成功添加！', 'success')
        # 返回一个 JSON 响应，告知前端提交成功
        return {'success': True}
    return render_template('gov_help.html')


@app.route('/reply_issues/<int:id>', methods=['GET', 'POST'])
def reply_issues(id):
    issue = Issue.query.get_or_404(id)  # 获取指定ID的记录，如果记录不存在则返回404

    if request.method == 'POST':
        # 获取表单数据
        name = request.form.get('name')
        phone = request.form.get('phone')
        description = request.form.get('description')
        title = request.form.get('title')
        reply = request.form.get('reply')

        # 更新记录
        issue.name = name
        issue.description = description
        issue.phone = phone
        issue.title = title
        issue.reply = reply
        issue.reply_date = datetime.now()  # 设置当前时间为回复时间
        db.session.commit()  # 提交更改
        flash('内容更新成功!', 'success')  # 显示成功消息
        return {'success': True}

    return render_template('reply_issue.html', issue=issue)


@app.route('/issues/delete/<int:id>/', methods=['POST'])
def delete_issue(id):
    issue = Issue.query.get_or_404(id)
    db.session.delete(issue)
    db.session.commit()
    flash('问题已成功删除！', 'success')
    return redirect(url_for('issues'))


@app.route('/ViewIssuesReplyAll/')
def ViewIssuesReplyAll():
    replies = Issue.query.filter(Issue.reply.isnot(None), Issue.reply != '').order_by(Issue.created_at.desc()).all()

    return render_template('view_issues_reply_all.html', replies=replies)


@app.route('/ViewReply/<int:reply_id>/')
def ViewReply(reply_id):

    reply = Issue.query.get_or_404(reply_id)

    return render_template('view_reply.html', reply=reply)


# @app.route('/view_notice/<int:notice_id>/')
# def view_notice(notice_id):
#     notice = Notification.query.get_or_404(notice_id)
#     return render_template('view_notice.html', notice=notice)
# -----------------------------------#


@app.route('/govNotice/')
def govNotice():
    # notices = Notice.query.all()
    notification = Notification.query.order_by(Notification.created_at.desc()).all()
    # User is not logged in
    return render_template('notice.html', notices=notification)


@app.route('/noticeAll/')
def noticeAll():
    # notices = Notice.query.all()
    notification = Notification.query.order_by(Notification.created_at.desc()).all()
    # User is not logged in
    return render_template('notice_all.html', notices=notification)


@app.route('/view_notice/<int:notice_id>/')
def view_notice(notice_id):
    notice = Notification.query.get_or_404(notice_id)
    return render_template('view_notice.html', notice=notice)


@app.route('/view_goods/<int:goods_id>/')
def view_goods(goods_id):
    goods = RecycledItem.query.get_or_404(goods_id)
    # 替换所有的反斜杠为正斜杠
    goods.image_url = goods.image_url.replace('static/', '')

    return render_template('view_goods.html', goods=goods)


@app.before_request
def before_request():
    g.user = None
    if 'username' in session:
        g.user = User.query.filter_by(username=session['username']).first()


@app.route('/test_mysql_connection')
def test_mysql_connection():
    db = get_db()
    if db:
        db.close()
        return jsonify({'message': 'Successfully connected to MySQL'})
    else:
        return jsonify({'message': 'Failed to connect to MySQL'})


# 主页
@app.route('/')
def home():
    return render_template('agricultureHome.html')


# 病虫害图像分类
@app.route('/pestClassify/')
def pestClassify():
    return render_template('PestClassification.html')


# 农产品回收
@app.route('/productRecycle/')
def productRecycle():
    items = RecycledItem.query.filter_by(is_putaway=True).all()  # 正确
    return render_template('productRecycle.html', displayitems=items)


# 政府帮扶
@app.route('/govHelp/')
def govHelp():
    return render_template('govHelp.html')


@app.route('/classify', methods=['POST'])
def upload_file():
    UPLOAD_FOLDER = 'static/html_crop/imgUploads'
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    # 确保上传文件夹存在
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        print(filename)
        print('ok')
        # 对文件进行处理，图像分类或其他操作
        # 处理结果为result
        model_path = "server/crop_classify/data/best.pth"
        class_names_path = "server/crop_classify/data/class_names_ch.txt"
        result = predict_top3_classes(model_path, class_names_path, filepath)
        categories = [pred[0] for pred in result]
        probabilities = [float(pred[1]) for pred in result]
        cg1 = categories[0]
        cg2 = categories[1]
        cg3 = categories[2]
        pr1 = probabilities[0]
        pr2 = probabilities[1]
        pr3 = probabilities[2]
        data = {
            'cg1': cg1,
            'cg2': cg2,
            'cg3': cg3,
            'pr1': pr1,
            'pr2': pr2,
            'pr3': pr3,
            'filename': filename
        }
        print(data)

        # 重定向到分类结果页面，并传递分类结果
        return jsonify({'redirect_url': '/Classified/', 'result': data})


# 病虫害图像分类结果
@app.route('/Classified/')
def Classified():
    return render_template('result.html')


if __name__ == '__main__':
    app.run(port=8899, debug=True)
