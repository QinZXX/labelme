import argparse
import codecs
import logging
import os
import os.path as osp
import sys
import yaml

from qtpy import QtCore
from qtpy import QtWidgets

from labelme import __appname__
from labelme import __version__
from labelme.app import MainWindow
from labelme.config import get_config
from labelme.logger import logger
from labelme.utils import newIcon

from PyQt5 import QtGui # 添加背景图
from PyQt5.Qt import *  ######

import labelme.glo as glo  # customize
# def main():
glo._init() # 字典的键不可以重复，添加的最后一个值会覆盖前面的值

userid="111" # 全局变量，记录用户名信息
glo.set_value("userid",userid)
password="456"
AccountFlag=False # 判定用户名和密码是否正确匹配的flag

###############
class LogWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("登陆界面")
        self.setWindowIcon(QIcon(".\\icons\\zhenshi.ico"))
        self.resize(500, 300)
        self.Password = "12345678" # 默认密码和用户名
        self.TaskName = "交通" # "人脸"
        self.UserName = None
        self.Co_Width = 40
        self.Co_Heigth = 20
        self.setup_ui()

    def setup_ui(self):
        self.lab_l = QLabel("帐户:", self)  # 帐户标签
        self.Lin_l = QLineEdit(self)  # 帐户录入框
        self.lab_p = QLabel("密码", self) # 密码标签
        self.Lin_p = QLineEdit(self) # 密码输入框
        self.Lin_p.setEchoMode(QLineEdit.Password)  # 设置密文显示
        self.lab_t = QLabel("任务:", self)  # 任务标签
        self.comboBox= QComboBox(self) # 任务类型，下拉选择框
        self.comboBox.addItem("人脸和智慧交通")
        self.comboBox.addItem("车牌")
        self.Pu_l = QPushButton(QIcon(".\\labelme\\icons\\zhenshi.ico"), "登陆", self)  # 登陆按钮
        self.Pu_l.clicked.connect(self.Login)

        palette1 = QtGui.QPalette() # 设置背景图片#########
        # palette1.setColor(self.backgroundRole(), QColor(192, 253, 123))  # 设置背景颜色
        palette1.setBrush(self.backgroundRole(), QtGui.QBrush(QtGui.QPixmap('.\\labelme\\icons\\1.jpg')))   # 设置背景图片
        self.setPalette(palette1)

    def resizeEvent(self, evt):  # 重新设置控件座标事件
        # 帐户标签
        self.lab_l.resize(self.Co_Width, self.Co_Heigth) # 设置大小
        self.lab_l.move(self.width() / 3, self.height() / 5) # 设置移动的位置
        # 帐户录入框
        self.Lin_l.move(self.lab_l.x() + self.lab_l.width(), self.lab_l.y()) # 录入框移动到标签左侧
        # 密码标签
        self.lab_p.resize(self.Co_Width, self.Co_Heigth)
        self.lab_p.move(self.lab_l.x(), self.lab_l.y() + self.lab_l.height() * 2)
        # 密码录入框
        self.Lin_p.move(self.lab_p.x() + self.lab_p.width(), self.lab_p.y())
        # 任务标签
        self.lab_t.resize(self.Co_Width, self.Co_Heigth)
        self.lab_t.move(self.lab_p.x(), self.lab_p.y() + self.lab_p.height() * 2)
        # 任务下拉框
        self.comboBox.move(self.lab_t.x() + self.lab_t.width(), self.lab_t.y()) # 修改坐标
        # 登陆按钮
        self.Pu_l.move(self.comboBox.x() + self.comboBox.width() / 4, self.lab_t.y() + self.lab_t.width())

    def Login(self):
        if (self.Lin_l.text()=="123") and (self.Lin_p.text()=="456"):
            global AccountFlag
            AccountFlag = True
        if (AccountFlag==True):
            global userid
            userid = self.Lin_l.text() # 将正确的userid保存到全局变量中
            glo.set_value("userid",userid)
            self.close()  # 关闭登陆界面
        # main()
        # app.setApplicationName(__appname__)
        # app.setWindowIcon(newIcon('icon'))
        # app.installTranslator(translator)
            win = MainWindow(
                config=config,
                filename=filename,
                output_file=output_file,
                output_dir=output_dir,
            )

            if reset_config:
                logger.info('Resetting Qt config: %s' % win.settings.fileName())
                win.settings.clear()
                sys.exit(0)

            win.show()  # 标注界面
            win.raise_() # 设置控件在最上层
            # sys.exit(app.exec_())
            # print("用户已登录，跳转至主界面")
        else:
            print('用户名与密码不匹配，请重新输入!')

    def keyPressEvent(self, event): # 添加enter键
        if event.key() == 16777220: #
            self.Login()


###########

# this main block is required to generate executable by pyinstaller
if __name__ == '__main__':
    # main()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--version', '-V', action='store_true', help='show version'
    )
    parser.add_argument(
        '--reset-config', action='store_true', help='reset qt config'
    )
    parser.add_argument(
        '--logger-level',
        default='info',
        choices=['debug', 'info', 'warning', 'fatal', 'error'],
        help='logger level',
    )
    parser.add_argument('filename', nargs='?', help='image or label filename')
    parser.add_argument(
        '--output',
        '-O',
        '-o',
        help='output file or directory (if it ends with .json it is '
             'recognized as file, else as directory)'
    )
    default_config_file = os.path.join(os.path.expanduser('~'), '.labelmerc') # 配置文件
    # 函数：把path中包含的"~"和"~user"转换成用户目录
    parser.add_argument(
        '--config',
        dest='config',
        help='config file or yaml-format string (default: {})'.format(
            default_config_file
        ),
        default=default_config_file,
    )
    # config for the gui
    parser.add_argument(
        '--nodata',
        dest='store_data',
        action='store_false',
        help='stop storing image data to JSON file',
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        '--autosave',
        dest='auto_save',
        action='store_true',
        help='auto save',
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        '--nosortlabels',
        dest='sort_labels',
        action='store_false',
        help='stop sorting labels',
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        '--flags',
        help='comma separated list of flags OR file containing flags',
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        '--labelflags',
        dest='label_flags',
        help='yaml string of label specific flags OR file containing json '
             'string of label specific flags (ex. {person-\d+: [male, tall], '
             'dog-\d+: [black, brown, white], .*: [occluded]})',  # NOQA
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        '--labels',
        help='comma separated list of labels OR file containing labels',
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        '--validatelabel',
        dest='validate_label',
        choices=['exact'],
        help='label validation types',
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        '--keep-prev',
        action='store_true',
        help='keep annotation of previous frame',
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        '--epsilon',
        type=float,
        help='epsilon to find nearest vertex on canvas',
        default=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    if args.version:
        print('{0} {1}'.format(__appname__, __version__))
        sys.exit(0)

    logger.setLevel(getattr(logging, args.logger_level.upper()))

    if hasattr(args, 'flags'):
        if os.path.isfile(args.flags):
            with codecs.open(args.flags, 'r', encoding='utf-8') as f:
                args.flags = [l.strip() for l in f if l.strip()]
        else:
            args.flags = [l for l in args.flags.split(',') if l]

    if hasattr(args, 'labels'):
        if os.path.isfile(args.labels):
            with codecs.open(args.labels, 'r', encoding='utf-8') as f:
                args.labels = [l.strip() for l in f if l.strip()]
        else:
            args.labels = [l for l in args.labels.split(',') if l]

    if hasattr(args, 'label_flags'):
        if os.path.isfile(args.label_flags):
            with codecs.open(args.label_flags, 'r', encoding='utf-8') as f:
                args.label_flags = yaml.safe_load(f)
        else:
            args.label_flags = yaml.safe_load(args.label_flags)

    config_from_args = args.__dict__
    config_from_args.pop('version')
    reset_config = config_from_args.pop('reset_config')
    filename = config_from_args.pop('filename')
    output = config_from_args.pop('output')
    config_file_or_yaml = config_from_args.pop('config')
    config = get_config(config_file_or_yaml, config_from_args)

    if not config['labels'] and config['validate_label']:
        logger.error('--labels must be specified with --validatelabel or '
                     'validate_label: true in the config file '
                     '(ex. ~/.labelmerc).')
        sys.exit(1)

    output_file = None
    output_dir = None
    if output is not None:
        if output.endswith('.json'):
            output_file = output
        else:
            output_dir = output

    translator = QtCore.QTranslator()
    translator.load(
        QtCore.QLocale.system().name(),
        osp.dirname(osp.abspath(__file__)) + '/translate'
    )

    app = QtWidgets.QApplication(sys.argv)


    Win = LogWindow() # 登录
    Win.show()

    # app = QApplication(sys.argv)

    sys.exit(app.exec_())
    # 闪烁 未定义确切退出
