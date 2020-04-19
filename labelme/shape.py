import copy
import math

from qtpy import QtCore
from qtpy import QtGui

import labelme.utils
import time  # 记录时间

# TODO(unknown):
# - [opt] Store paths instead of creating new ones at each paint.


R, G, B = SHAPE_COLOR = 0, 255, 0  # green
DEFAULT_LINE_COLOR = QtGui.QColor(R, G, B, 128)                # bf hovering
DEFAULT_FILL_COLOR = QtGui.QColor(R, G, B, 128)                # hovering
DEFAULT_SELECT_LINE_COLOR = QtGui.QColor(255, 255, 255)        # selected
DEFAULT_SELECT_FILL_COLOR = QtGui.QColor(R, G, B, 155)         # selected
DEFAULT_VERTEX_FILL_COLOR = QtGui.QColor(R, G, B, 255)         # hovering
DEFAULT_HVERTEX_FILL_COLOR = QtGui.QColor(255, 255, 255, 255)  # hovering


class Shape(object):

    P_SQUARE, P_ROUND = 0, 1

    MOVE_VERTEX, NEAR_VERTEX = 0, 1

    # The following class variables influence the drawing of all shape objects.
    line_color = DEFAULT_LINE_COLOR
    fill_color = DEFAULT_FILL_COLOR
    select_line_color = DEFAULT_SELECT_LINE_COLOR
    select_fill_color = DEFAULT_SELECT_FILL_COLOR
    vertex_fill_color = DEFAULT_VERTEX_FILL_COLOR
    hvertex_fill_color = DEFAULT_HVERTEX_FILL_COLOR
    point_type = P_ROUND
    point_size = 8
    scale = 1.0

    def __init__(self, label=None, line_color=None, shape_type=None,
                 flags=None, group_id=None):
        self.label = label
        self.group_id = group_id
        self.points = []
        self.pointsNew = [] # 新增  所有的变换都要加入这个里面
        self.fill = False
        self.selected = False
        self.shape_type = shape_type
        self.flags = flags
        self.other_data = {}

        self._highlightIndex = None
        self._highlightMode = self.NEAR_VERTEX
        self._highlightSettings = {
            self.NEAR_VERTEX: (4, self.P_ROUND),
            self.MOVE_VERTEX: (1.5, self.P_SQUARE),
        }

        self._closed = False

        if line_color is not None:
            # Override the class line_color attribute
            # with an object attribute. Currently this
            # is used for drawing the pending line a different color.
            self.line_color = line_color

        self.shape_type = shape_type

    @property
    def shape_type(self):
        return self._shape_type

    @shape_type.setter
    def shape_type(self, value):
        if value is None:
            value = 'polygon'
        if value not in ['polygon', 'rectangle', 'point',
           'line', 'circle', 'linestrip']:
            raise ValueError('Unexpected shape_type: {}'.format(value))
        self._shape_type = value

    def close(self):
        self._closed = True

    def addPoint(self, point): # points 列表的列表（坐标）
        if self.points and point == self.points[0]: # 如果点不空（空列表为False），并且point等于points第一个点坐标（封闭），则close
            self.close()
        else:
            time_str= time.strftime('%m-%d %H:%M:%S', time.localtime(time.time())) # 添加时间
            self.points.append(point)
            self.pointsNew.append([point.x(),point.y(),time_str]) # 添加时间坐标  （调用的地方也要修改）  用此点类重新定义一个类？不好，其他位置要改变  还是只用这个  其他绘制的地方有需要用到这个

    def canAddPoint(self):
        return self.shape_type in ['polygon', 'linestrip']

    def popPoint(self):
        if self.points:
            self.pointsNew.pop() # 新增
            return self.points.pop()
        return None

    def insertPoint(self, i, point): # 插入点  变化的是points类，需要改用到points类的所有地方（调用points绘制画面，添加points到容器用于后续保存，{添加点，弹出点，移动点，插入点}）
        time_str = time.strftime('%m-%d %H:%M:%S', time.localtime(time.time()))
        self.points.insert(i, point)
        self.pointsNew.insert(i, [point.x(),point.y(),time_str]) # 添加时间

    def removePoint(self, i):
        self.points.pop(i)
        self.pointsNew.pop(i) ###

    def isClosed(self):
        return self._closed

    def setOpen(self):
        self._closed = False

    def getRectFromLine(self, pt1, pt2): # 给pt1添加变量pt.t()   这里怎么解决？？  参数是点  而不是points，就需要改调用这个函数的地方，这个函数获取两点的坐标并返回对应的qt矩形类
        x1, y1 = pt1.x(), pt1.y()   # 直接在这里改吧，后面通过解包的方式  把这里的pt1和pt2就改成三个坐标的点
        x2, y2 = pt2.x(), pt2.y()
        return QtCore.QRectF(x1, y1, x2 - x1, y2 - y1) # 矩形绘制

    def paint(self, painter): # 绘制部分 调用points类 参数Qpainter类
        if self.points:
            color = self.select_line_color \
                if self.selected else self.line_color
            pen = QtGui.QPen(color)
            # Try using integer sizes for smoother drawing(?)
            pen.setWidth(max(1, int(round(2.0 / self.scale))))
            painter.setPen(pen)

            line_path = QtGui.QPainterPath()
            vrtx_path = QtGui.QPainterPath()

            if self.shape_type == 'rectangle':
                assert len(self.points) in [1, 2]
                if len(self.points) == 2:
                    rectangle = self.getRectFromLine(*self.points) # 现在长度为3了，要修改  参数为两个点的坐标  直接修改那个那个函数  要出错，因为传入的不是list类的点，而是Qt点类
                    line_path.addRect(rectangle)
                for i in range(len(self.points)): # 画顶点
                    self.drawVertex(vrtx_path, i) # 绘制
            elif self.shape_type == "circle":
                assert len(self.points) in [1, 2]
                if len(self.points) == 2:
                    rectangle = self.getCircleRectFromLine(self.points) # 点类
                    line_path.addEllipse(rectangle)
                for i in range(len(self.points)):
                    self.drawVertex(vrtx_path, i) # 绘制
            elif self.shape_type == "linestrip": # 折线
                line_path.moveTo(self.points[0]) # Qt点类啊卧榻  获取点的前两个坐标x,y，再转为Qt点类
                for i, p in enumerate(self.points):
                    line_path.lineTo(p) # p也要转为Qt点类
                    self.drawVertex(vrtx_path, i)
            else:
                line_path.moveTo(self.points[0]) # 转
                # Uncommenting the following line will draw 2 paths
                # for the 1st vertex, and make it non-filled, which
                # may be desirable.
                # self.drawVertex(vrtx_path, 0)

                for i, p in enumerate(self.points):
                    line_path.lineTo(p) # 转  要不直接在外部新定义一个pointsOld，把新的含三个坐标的points转成pointsOld，再把这些points改成pointsOld
                    self.drawVertex(vrtx_path, i)
                if self.isClosed():
                    line_path.lineTo(self.points[0])

            painter.drawPath(line_path)
            painter.drawPath(vrtx_path)
            painter.fillPath(vrtx_path, self._vertex_fill_color)
            if self.fill:
                color = self.select_fill_color \
                    if self.selected else self.fill_color
                painter.fillPath(line_path, color)

    def drawVertex(self, path, i): # 绘制  这样新建存储就不用更改这些绘制的函数
        d = self.point_size / self.scale
        shape = self.point_type
        point = self.points[i]
        if i == self._highlightIndex:
            size, shape = self._highlightSettings[self._highlightMode]
            d *= size
        if self._highlightIndex is not None:
            self._vertex_fill_color = self.hvertex_fill_color
        else:
            self._vertex_fill_color = self.vertex_fill_color
        if shape == self.P_SQUARE:
            path.addRect(point.x() - d / 2, point.y() - d / 2, d, d)
        elif shape == self.P_ROUND:
            path.addEllipse(point, d / 2.0, d / 2.0)
        else:
            assert False, "unsupported vertex shape"

    def nearestVertex(self, point, epsilon): # 最近顶点
        min_distance = float('inf')
        min_i = None
        for i, p in enumerate(self.points):
            dist = labelme.utils.distance(p - point)
            if dist <= epsilon and dist < min_distance:
                min_distance = dist
                min_i = i
        return min_i

    def nearestEdge(self, point, epsilon): # 最近边
        min_distance = float('inf')
        post_i = None
        for i in range(len(self.points)):
            line = [self.points[i - 1], self.points[i]]
            dist = labelme.utils.distancetoline(point, line)
            if dist <= epsilon and dist < min_distance:
                min_distance = dist
                post_i = i
        return post_i

    def containsPoint(self, point): # 包含点
        return self.makePath().contains(point)

    def getCircleRectFromLine(self, line): # 得到圆和矩形从line中
        """Computes parameters to draw with `QPainterPath::addEllipse`"""
        if len(line) != 2:
            return None
        (c, point) = line
        r = line[0] - line[1]
        d = math.sqrt(math.pow(r.x(), 2) + math.pow(r.y(), 2))
        rectangle = QtCore.QRectF(c.x() - d, c.y() - d, 2 * d, 2 * d)
        return rectangle

    def makePath(self): # 生成路径
        if self.shape_type == 'rectangle':
            path = QtGui.QPainterPath()
            if len(self.points) == 2:
                rectangle = self.getRectFromLine(*self.points)
                path.addRect(rectangle)
        elif self.shape_type == "circle":
            path = QtGui.QPainterPath()
            if len(self.points) == 2:
                rectangle = self.getCircleRectFromLine(self.points)
                path.addEllipse(rectangle)
        else:
            path = QtGui.QPainterPath(self.points[0])
            for p in self.points[1:]:
                path.lineTo(p)
        return path

    def boundingRect(self): # 边界矩形
        return self.makePath().boundingRect()

    def moveBy(self, offset): # 移动偏移(x,y)
        self.points = [p + offset for p in self.points]

    def moveVertexBy(self, i, offset): # 移动某个顶点
        self.points[i] = self.points[i] + offset

    def highlightVertex(self, i, action): # 高亮顶点
        self._highlightIndex = i
        self._highlightMode = action

    def highlightClear(self): # 高亮clear
        self._highlightIndex = None

    def copy(self): # 复制
        return copy.deepcopy(self)

    def __len__(self):
        return len(self.points) # 获取shape中点的个数

    def __getitem__(self, key): #得到某个点的坐标  添加下标操作
        return self.points[key]

    def __setitem__(self, key, value): # 设定某个点的坐标
        self.points[key] = value
        # 添加时间戳
        time_str = time.strftime('%m-%d %H:%M:%S', time.localtime(time.time()))  # 添加时间
        self.pointsNew[key] = [value.x(),value.y(),time_str] # 设置点  这个也要耕者改变
