from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets

from labelme import QT5
from labelme.shape import Shape
import labelme.utils

import time  # 添加记录时间
# TODO(unknown):
# - [maybe] Find optimal epsilon value.


CURSOR_DEFAULT = QtCore.Qt.ArrowCursor
CURSOR_POINT = QtCore.Qt.PointingHandCursor
CURSOR_DRAW = QtCore.Qt.CrossCursor
CURSOR_MOVE = QtCore.Qt.ClosedHandCursor
CURSOR_GRAB = QtCore.Qt.OpenHandCursor


class Canvas(QtWidgets.QWidget): # 显示和绘制图片的控件

    zoomRequest = QtCore.Signal(int, QtCore.QPoint)
    scrollRequest = QtCore.Signal(int, int)
    newShape = QtCore.Signal()
    selectionChanged = QtCore.Signal(list) # 选择改变的信号函数
    shapeMoved = QtCore.Signal() # shape改变的信号
    drawingPolygon = QtCore.Signal(bool) # 绘制多边形的信号
    edgeSelected = QtCore.Signal(bool, object) # 选择边的信号
    vertexSelected = QtCore.Signal(bool) # 选择顶点的信号

    CREATE, EDIT = 0, 1  # 两种模式，绘制模式和编辑模式

    # polygon, rectangle, line, or point
    _createMode = 'polygon' # 绘制模式默认为多边形

    _fill_drawing = False # shape填充默认为false

    def __init__(self, *args, **kwargs):
        self.epsilon = kwargs.pop('epsilon', 10.0) # 把字典中的epsilon删除，如果此键不存在则返回10.0。存在则删除此键的键值对，并返回键对应的值
        self.double_click = kwargs.pop('double_click', 'close') #双击
        if self.double_click not in [None, 'close']: #如果双击 的值不是None也不是关闭
            raise ValueError(
                'Unexpected value for double_click event: {}'
                .format(self.double_click) # 非期望值
            )
        super(Canvas, self).__init__(*args, **kwargs)
        # Initialise local state.
        self.mode = self.EDIT # 模式选择
        self.shapes = [] # shapes
        self.shapesBackups = [] # shapes backup
        self.current = None # 当前的什么 None值
        self.selectedShapes = []  # save the selected shapes here
        self.selectedShapesCopy = [] # 上一个成员的copy
        # self.line represents:
        #   - createMode == 'polygon': edge from last point to current
        #   - createMode == 'rectangle': diagonal line of the rectangle
        #   - createMode == 'line': the line
        #   - createMode == 'point': the point
        self.line = Shape() # 一个Shape类对象，用于在图像绘制多边形
        self.prevPoint = QtCore.QPoint() # baocun
        self.prevMovePoint = QtCore.QPoint() # 保存当前点位置
        self.offsets = QtCore.QPoint(), QtCore.QPoint() #偏移是两个空点，出事为0
        self.scale = 1.0 #放缩比例
        self.pixmap = QtGui.QPixmap() # pixmap绘图设备的图像显示
        self.visible = {} # 可见的
        self._hideBackround = False # 是否隐藏背景
        self.hideBackround = False
        self.hShape = None # 当前shape？
        self.prevhShape = None # 上一个shape
        self.hVertex = None #当前顶点
        self.prevhVertex = None # 上一个顶点
        self.hEdge = None # 当前边
        self.prevhEdge = None # 上一条边
        self.movingShape = False # 移动形状
        self._painter = QtGui.QPainter() # 绘制控件   在父类上绘制
        self._cursor = CURSOR_DEFAULT #光标样式设置
        # Menus:
        # 0: right-click without selection and dragging of shapes
        # 1: right-click with selection and dragging of shapes
        self.menus = (QtWidgets.QMenu(), QtWidgets.QMenu()) #0:右键没有选择 1:拖拽形状
        # Set widget options.
        self.setMouseTracking(True) # 设置部件选择  鼠标跟踪设为真（此时可以重载几个鼠标的槽函数），参数为鼠标的信号
        self.setFocusPolicy(QtCore.Qt.WheelFocus) # 设置焦点策略 轮子焦点

    def fillDrawing(self): # 是否填充
        return self._fill_drawing

    def setFillDrawing(self, value): # 改变填充方式
        self._fill_drawing = value

    @property
    def createMode(self):
        return self._createMode

    @createMode.setter
    def createMode(self, value):
        if value not in ['polygon', 'rectangle', 'circle',
           'line', 'point', 'linestrip']:
            raise ValueError('Unsupported createMode: %s' % value)
        self._createMode = value

    def storeShapes(self): ## 完成一个标注，将shape保存到shapes里边
        shapesBackup = []
        for shape in self.shapes:
            shapesBackup.append(shape.copy()) # 把所有的shapes保存到这个里面
        if len(self.shapesBackups) >= 10: # 如果
            self.shapesBackups = self.shapesBackups[-9:]
        self.shapesBackups.append(shapesBackup)

    @property
    def isShapeRestorable(self):
        if len(self.shapesBackups) < 2: ### 是否可保存  
            return False
        return True

    def restoreShape(self): # 重置（恢复）shape
        if not self.isShapeRestorable: # 如果不可存
            return
        self.shapesBackups.pop()  # latest # 列表弹出末尾元素
        shapesBackup = self.shapesBackups.pop() # 形状支持
        self.shapes = shapesBackup # shapes就等于这个backup
        self.selectedShapes = [] # 保存选择的多个shape
        for shape in self.shapes: # 对于支持的形状shapes，默认选择shape的标志全部设置为False
            shape.selected = False # 设置为空
        self.repaint() # 重绘

    def enterEvent(self, ev): # 鼠标进入控件事件
        self.overrideCursor(self._cursor) # 返回当前鼠标形状的QCursor 对象

    def leaveEvent(self, ev): # 鼠标离开控件事件
        self.unHighlight() # 不在高亮
        self.restoreCursor() # 取消全局鼠标形状设置

    def focusOutEvent(self, ev): #
        self.restoreCursor() # 取消全局鼠标形状设置

    def isVisible(self, shape):
        return self.visible.get(shape, True)

    def drawing(self): # 返回bool 是否绘制状态
        return self.mode == self.CREATE

    def editing(self): # 编辑状态
        return self.mode == self.EDIT

    def setEditing(self, value=True): # 设置编辑状态
        self.mode = self.EDIT if value else self.CREATE
        if not value:  # Create
            self.unHighlight()
            self.deSelectShape()

    def unHighlight(self): # 取消高亮
        if self.hShape:
            self.hShape.highlightClear()
            self.update()
        self.prevhShape = self.hShape
        self.prevhVertex = self.hVertex
        self.prevhEdge = self.hEdge
        self.hShape = self.hVertex = self.hEdge = None

    def selectedVertex(self): # 顶点
        return self.hVertex is not None

    def mouseMoveEvent(self, ev): # 鼠标移动检测， 每次移动都更新点到self.prevMovePoint
        """Update line with last point and current coordinates."""
        try:
            if QT5:
                pos = self.transformPos(ev.localPos()) # 获取坐标
            else:
                pos = self.transformPos(ev.posF())
        except AttributeError:
            return

        self.prevMovePoint = pos
        self.restoreCursor()

        # Polygon drawing.
        if self.drawing():
            self.line.shape_type = self.createMode

            self.overrideCursor(CURSOR_DRAW)  # 重置光标
            if not self.current:
                return

            if self.outOfPixmap(pos): # 如果坐标在pixmap外 不让用户在pixmap外部绘制
                # Don't allow the user to draw outside the pixmap.
                # Project the point to the pixmap's edges.
                pos = self.intersectionPoint(self.current[-1], pos) # 将点投影到pixmap控件的边缘
            elif len(self.current) > 1 and self.createMode == 'polygon' and\
                    self.closeEnough(pos, self.current[0]): # 否则，如果当前shape的点个数大于1 并且模式为绘制多边形 并且足够关闭(pos，shape的第一个元素)？
                # Shape类对象有下标操作？(设定__getitem__函数即可)
                # Attract line to starting point and
                # colorise to alert the user.
                pos = self.current[0] # 提取line到起始点并且用彩色点提醒用户
                self.overrideCursor(CURSOR_POINT) # 更改光标样式为点
                self.current.highlightVertex(0, Shape.NEAR_VERTEX) # 高亮顶点
            if self.createMode in ['polygon', 'linestrip']: # 如果模式为多边形和折线
                self.line[0] = self.current[-1] # line[0]为当前shape的最后一个点的元素
                self.line[1] = pos # line[1]为当前元素
            elif self.createMode == 'rectangle': # 如果绘制矩形
                self.line.points = [self.current[0], pos] # line.points为第一个点和当前点  su
                self.line.close() # 把点保存进矩阵并且加相关信息（类别名）
            elif self.createMode == 'circle': # 圆形
                self.line.points = [self.current[0], pos] # 添加两点
                self.line.shape_type = "circle" # 形状设置为圆
            elif self.createMode == 'line': # 线段
                self.line.points = [self.current[0], pos] # 添加两点
                self.line.close() # 关闭保存
            elif self.createMode == 'point': # 点
                self.line.points = [self.current[0]] # 添加点
                self.line.close() # 关闭保存
            self.repaint() # 重绘
            self.current.highlightClear() # 高亮清除
            return

        # Polygon copy moving.
        if QtCore.Qt.RightButton & ev.buttons(): # 移动
            if self.selectedShapesCopy and self.prevPoint: # 复制
                self.overrideCursor(CURSOR_MOVE) # 光标改变
                self.boundedMoveShapes(self.selectedShapesCopy, pos) # 框处移动
                self.repaint() # 重绘
            elif self.selectedShapes: # 选择形状
                self.selectedShapesCopy = \
                    [s.copy() for s in self.selectedShapes] # 形状
                self.repaint()
            return

        # Polygon/Vertex moving.
        if QtCore.Qt.LeftButton & ev.buttons(): # 多边形移动
            if self.selectedVertex():
                self.boundedMoveVertex(pos)
                self.repaint()
                self.movingShape = True
            elif self.selectedShapes and self.prevPoint:
                self.overrideCursor(CURSOR_MOVE)
                self.boundedMoveShapes(self.selectedShapes, pos)
                self.repaint()
                self.movingShape = True
            return

        # Just hovering over the canvas, 2 possibilities:
        # - Highlight shapes
        # - Highlight vertex
        # Update shape/vertex fill and tooltip value accordingly.
        self.setToolTip(self.tr("Image")) # 设置提示
        for shape in reversed([s for s in self.shapes if self.isVisible(s)]): # self.shapes保存的，如果shape是可见的，便执行
            # Look for a nearby vertex to highlight. If that fails,
            # check if we happen to be inside a shape.
            index = shape.nearestVertex(pos, self.epsilon / self.scale) # 查找最近顶点
            index_edge = shape.nearestEdge(pos, self.epsilon / self.scale) # 最近边
            if index is not None: # 如果index
                if self.selectedVertex():
                    self.hShape.highlightClear()
                self.prevhVertex = self.hVertex = index # 更新形状 顶点 边
                self.prevhShape = self.hShape = shape
                self.prevhEdge = self.hEdge = index_edge
                shape.highlightVertex(index, shape.MOVE_VERTEX) # 高亮顶点
                self.overrideCursor(CURSOR_POINT) # 光标样式
                self.setToolTip(self.tr("Click & drag to move point")) # 点击或拖拽移动点
                self.setStatusTip(self.toolTip()) # 设置状态提示
                self.update() # 更新窗口部件，速度比repaint更快，闪烁更少
                break
            elif shape.containsPoint(pos): # 如果此形状shape里包含当前点
                if self.selectedVertex():
                    self.hShape.highlightClear()
                self.prevhVertex = self.hVertex
                self.hVertex = None
                self.prevhShape = self.hShape = shape
                self.prevhEdge = self.hEdge = index_edge
                self.setToolTip(
                    self.tr("Click & drag to move shape '%s'") % shape.label)
                self.setStatusTip(self.toolTip())
                self.overrideCursor(CURSOR_GRAB)
                self.update()
                break
        else:  # Nothing found, clear highlights, reset state.
            self.unHighlight()
        self.edgeSelected.emit(self.hEdge is not None, self.hShape)
        self.vertexSelected.emit(self.hVertex is not None)

    def addPointToEdge(self):# 添加点到边
        shape = self.prevhShape # 上一个形状
        index = self.prevhEdge # 上一条边的index
        point = self.prevMovePoint # 上一个移动点
        if shape is None or index is None or point is None: #形状不空 或 index 或 点也存在
            return
        shape.insertPoint(index, point) # 插入点
        shape.highlightVertex(index, shape.MOVE_VERTEX)
        self.hShape = shape # 当前形状
        self.hVertex = index # index
        self.hEdge = None # 当前边重置
        self.movingShape = True #一同shape设为True

    def removeSelectedPoint(self): # 删除选择的点  这些都会导致shape内点的变化  都要在这里添加新shape的修改
        shape = self.prevhShape
        point = self.prevMovePoint
        if shape is None or point is None:
            return
        index = shape.nearestVertex(point, self.epsilon)
        shape.removePoint(index) # 最近点移除
        # shape.highlightVertex(index, shape.MOVE_VERTEX)
        self.hShape = shape
        self.hVertex = None
        self.hEdge = None
        self.movingShape = True  # Save changes

    def mousePressEvent(self, ev):
        if QT5:
            pos = self.transformPos(ev.localPos()) ####  获取坐标 两个类型都是<class 'PyQt5.QtCore.QPointF'>  此函数用于变换坐标到对应控件？
            t_str = time.strftime('%m-%d %H:%M:%S', time.localtime(time.time()))  ## 添加记录时间  汉化文件行数变化
        else:
            pos = self.transformPos(ev.posF())
        if ev.button() == QtCore.Qt.LeftButton: # 左键则绘制，  一边添加
            if self.drawing():
                if self.current: # 如果当前的shape不为空（points内有点）
                    # Add point to existing shape.
                    if self.createMode == 'polygon':
                        self.current.addPoint(self.line[1]) # 添加点 此时pointsNew也变化
                        self.line[0] = self.current[-1] # 等于最后一个点line[0]
                        if self.current.isClosed(): # 通过此函数找到了self.current的类别，即Shape
                            self.finalise() # 敲定
                    elif self.createMode in ['rectangle', 'circle', 'line']:
                        assert len(self.current.points) == 1
                        self.current.points = self.line.points
                        self.finalise()
                    elif self.createMode == 'linestrip':
                        self.current.addPoint(self.line[1])
                        self.line[0] = self.current[-1]
                        if int(ev.modifiers()) == QtCore.Qt.ControlModifier:
                            self.finalise()
                elif not self.outOfPixmap(pos):
                    # Create new shape.
                    self.current = Shape(shape_type=self.createMode)
                    self.current.addPoint(pos) #  这里添加的两个坐标的点了  看下位置  加入哪里的
                    if self.createMode == 'point':
                        self.finalise()
                    else:
                        if self.createMode == 'circle':
                            self.current.shape_type = 'circle' # 圆
                        self.line.points = [pos, pos] # 两点
                        self.setHiding() #
                        self.drawingPolygon.emit(True) # 绘制
                        self.update() # 刷新
            else: # 没有点，起始
                group_mode = (int(ev.modifiers()) == QtCore.Qt.ControlModifier) # 鼠标信息的修改器 与 控制器修改器
                self.selectShapePoint(pos, multiple_selection_mode=group_mode) # 选择点
                self.prevPoint = pos  # 更新点
                self.repaint() # 重绘
        elif ev.button() == QtCore.Qt.RightButton and self.editing(): # 右键
            group_mode = (int(ev.modifiers()) == QtCore.Qt.ControlModifier)
            self.selectShapePoint(pos, multiple_selection_mode=group_mode)
            self.prevPoint = pos
            self.repaint()

    def mouseReleaseEvent(self, ev): # 鼠标右键释放 编辑状态
        if ev.button() == QtCore.Qt.RightButton:
            menu = self.menus[len(self.selectedShapesCopy) > 0]
            self.restoreCursor()
            if not menu.exec_(self.mapToGlobal(ev.pos())) \
                    and self.selectedShapesCopy:
                # Cancel the move by deleting the shadow copy.
                self.selectedShapesCopy = []
                self.repaint()
        elif ev.button() == QtCore.Qt.LeftButton and self.selectedShapes:
            self.overrideCursor(CURSOR_GRAB)

        if self.movingShape and self.hShape:
            index = self.shapes.index(self.hShape)
            if (self.shapesBackups[-1][index].points !=
                    self.shapes[index].points):
                self.storeShapes()
                self.shapeMoved.emit()

            self.movingShape = False

    def endMove(self, copy): # 结束移动
        assert self.selectedShapes and self.selectedShapesCopy
        assert len(self.selectedShapesCopy) == len(self.selectedShapes)
        if copy:
            for i, shape in enumerate(self.selectedShapesCopy):
                self.shapes.append(shape)
                self.selectedShapes[i].selected = False
                self.selectedShapes[i] = shape
        else:
            for i, shape in enumerate(self.selectedShapesCopy):
                self.selectedShapes[i].points = shape.points
        self.selectedShapesCopy = []
        self.repaint()
        self.storeShapes()
        return True

    def hideBackroundShapes(self, value): # 隐藏背景
        self.hideBackround = value
        if self.selectedShapes:
            # Only hide other shapes if there is a current selection.
            # Otherwise the user will not be able to select a shape.
            self.setHiding(True)
            self.repaint()

    def setHiding(self, enable=True):
        self._hideBackround = self.hideBackround if enable else False

    def canCloseShape(self):
        return self.drawing() and self.current and len(self.current) > 2

    def mouseDoubleClickEvent(self, ev): # 鼠标双击事件
        # We need at least 4 points here, since the mousePress handler
        # adds an extra one before this handler is called.
        if (self.double_click == 'close' and self.canCloseShape() and
                len(self.current) > 3): # 双击检测就关闭的标志打开，并且可关闭shape的标志打开，并且当前的shape的点的个数大于3（重载__len__()方法）
            self.current.popPoint() # 由此可见current类实际是Shape类  用来代表当前shape  弹出点
            self.finalise()

    def selectShapes(self, shapes):
        self.setHiding()
        self.selectionChanged.emit(shapes)
        self.update()

    def selectShapePoint(self, point, multiple_selection_mode):
        """Select the first shape created which contains this point."""
        if self.selectedVertex():  # A vertex is marked for selection.
            index, shape = self.hVertex, self.hShape
            shape.highlightVertex(index, shape.MOVE_VERTEX)
        else:
            for shape in reversed(self.shapes):
                if self.isVisible(shape) and shape.containsPoint(point):
                    self.calculateOffsets(shape, point)
                    self.setHiding()
                    if multiple_selection_mode:
                        if shape not in self.selectedShapes:
                            self.selectionChanged.emit(
                                self.selectedShapes + [shape])
                    else:
                        self.selectionChanged.emit([shape])
                    return
        self.deSelectShape()

    def calculateOffsets(self, shape, point):
        rect = shape.boundingRect()
        x1 = rect.x() - point.x()
        y1 = rect.y() - point.y()
        x2 = (rect.x() + rect.width() - 1) - point.x()
        y2 = (rect.y() + rect.height() - 1) - point.y()
        self.offsets = QtCore.QPoint(x1, y1), QtCore.QPoint(x2, y2)

    def boundedMoveVertex(self, pos):
        index, shape = self.hVertex, self.hShape
        point = shape[index]
        if self.outOfPixmap(pos):
            pos = self.intersectionPoint(point, pos)
        shape.moveVertexBy(index, pos - point)

    def boundedMoveShapes(self, shapes, pos):
        if self.outOfPixmap(pos):
            return False  # No need to move
        o1 = pos + self.offsets[0]
        if self.outOfPixmap(o1):
            pos -= QtCore.QPoint(min(0, o1.x()), min(0, o1.y()))
        o2 = pos + self.offsets[1]
        if self.outOfPixmap(o2):
            pos += QtCore.QPoint(min(0, self.pixmap.width() - o2.x()),
                                 min(0, self.pixmap.height() - o2.y()))
        # XXX: The next line tracks the new position of the cursor
        # relative to the shape, but also results in making it
        # a bit "shaky" when nearing the border and allows it to
        # go outside of the shape's area for some reason.
        # self.calculateOffsets(self.selectedShapes, pos)
        dp = pos - self.prevPoint
        if dp:
            for shape in shapes:
                shape.moveBy(dp)
            self.prevPoint = pos
            return True
        return False

    def deSelectShape(self):
        if self.selectedShapes:
            self.setHiding(False)
            self.selectionChanged.emit([])
            self.update()

    def deleteSelected(self):
        deleted_shapes = []
        if self.selectedShapes:
            for shape in self.selectedShapes:
                self.shapes.remove(shape)
                deleted_shapes.append(shape)
            self.storeShapes()
            self.selectedShapes = []
            self.update()
        return deleted_shapes

    def copySelectedShapes(self):
        if self.selectedShapes:
            self.selectedShapesCopy = [s.copy() for s in self.selectedShapes]
            self.boundedShiftShapes(self.selectedShapesCopy)
            self.endMove(copy=True)
        return self.selectedShapes

    def boundedShiftShapes(self, shapes):
        # Try to move in one direction, and if it fails in another.
        # Give up if both fail.
        point = shapes[0][0]
        offset = QtCore.QPoint(2.0, 2.0)
        self.offsets = QtCore.QPoint(), QtCore.QPoint()
        self.prevPoint = point
        if not self.boundedMoveShapes(shapes, point - offset):
            self.boundedMoveShapes(shapes, point + offset)

    def paintEvent(self, event): # 绘制事件
        if not self.pixmap:
            return super(Canvas, self).paintEvent(event)

        p = self._painter
        p.begin(self) # self？
        p.setRenderHint(QtGui.QPainter.Antialiasing) # 设置样式
        p.setRenderHint(QtGui.QPainter.HighQualityAntialiasing)
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)

        p.scale(self.scale, self.scale)
        p.translate(self.offsetToCenter()) # 翻译

        p.drawPixmap(0, 0, self.pixmap) # 绘制
        Shape.scale = self.scale
        for shape in self.shapes: # 绘制
            if (shape.selected or not self._hideBackround) and \
                    self.isVisible(shape):
                shape.fill = shape.selected or shape == self.hShape
                shape.paint(p)
        if self.current:
            self.current.paint(p)
            self.line.paint(p)
        if self.selectedShapesCopy:
            for s in self.selectedShapesCopy:
                s.paint(p)

        if (self.fillDrawing() and self.createMode == 'polygon' and
                self.current is not None and len(self.current.points) >= 2):
            drawing_shape = self.current.copy()
            drawing_shape.addPoint(self.line[1])
            drawing_shape.fill = True
            drawing_shape.fill_color.setAlpha(64)
            drawing_shape.paint(p)

        p.end()

    def transformPos(self, point): # 坐标变换函数  根据大小做变换  当前坐标为canvas控件
        """Convert from widget-logical coordinates to painter-logical ones."""
        return point / self.scale - self.offsetToCenter() # 返回point除以放缩比例减去当前偏离中心的位置

    def offsetToCenter(self):
        s = self.scale
        area = super(Canvas, self).size()
        w, h = self.pixmap.width() * s, self.pixmap.height() * s
        aw, ah = area.width(), area.height()
        x = (aw - w) / (2 * s) if aw > w else 0
        y = (ah - h) / (2 * s) if ah > h else 0
        return QtCore.QPoint(x, y) # 返回中心点类  初始化函数为QtCore.QPoint(x, y)

    def outOfPixmap(self, p): # 在pixmap之外
        w, h = self.pixmap.width(), self.pixmap.height()
        return not (0 <= p.x() <= w - 1 and 0 <= p.y() <= h - 1)

    def finalise(self): # 敲定（确定方案）
        assert self.current
        self.current.close() # Shape类方法，设定close标志位True
        self.shapes.append(self.current) # shapes添加当前shape  所以更改的保存shape的方法 把data里面的shapes里的shape里的points改成pointsNew
        self.storeShapes() # 重置shapes
        self.current = None # 当前设定为空
        self.setHiding(False) # 隐藏设为False
        self.newShape.emit() # 新形状
        self.update() # 更新

    def closeEnough(self, p1, p2):
        # d = distance(p1 - p2)
        # m = (p1-p2).manhattanLength()
        # print "d %.2f, m %d, %.2f" % (d, m, d - m)
        # divide by scale to allow more precision when zoomed in
        return labelme.utils.distance(p1 - p2) < (self.epsilon / self.scale)

    def intersectionPoint(self, p1, p2): # 交集点
        # Cycle through each image edge in clockwise fashion,
        # and find the one intersecting the current line segment.
        # http://paulbourke.net/geometry/lineline2d/
        # 顺时针循环通过每个图像边缘，并找到与当前线段相交的线段。
        size = self.pixmap.size()
        points = [(0, 0),
                  (size.width() - 1, 0),
                  (size.width() - 1, size.height() - 1),
                  (0, size.height() - 1)]
        # x1, y1 should be in the pixmap, x2, y2 should be out of the pixmap
        x1 = min(max(p1.x(), 0), size.width() - 1)
        y1 = min(max(p1.y(), 0), size.height() - 1)
        x2, y2 = p2.x(), p2.y()
        d, i, (x, y) = min(self.intersectingEdges((x1, y1), (x2, y2), points))
        x3, y3 = points[i]
        x4, y4 = points[(i + 1) % 4]
        if (x, y) == (x1, y1):
            # Handle cases where previous point is on one of the edges.
            if x3 == x4:
                return QtCore.QPoint(x3, min(max(0, y2), max(y3, y4)))
            else:  # y3 == y4
                return QtCore.QPoint(min(max(0, x2), max(x3, x4)), y3)
        return QtCore.QPoint(x, y)

    def intersectingEdges(self, point1, point2, points): # 找出交集边 每条由点形成的边，返回边长的一般  用来选择最近的边
        """Find intersecting edges.

        For each edge formed by `points', yield the intersection
        with the line segment `(x1,y1) - (x2,y2)`, if it exists.
        Also return the distance of `(x2,y2)' to the middle of the
        edge along with its index, so that the one closest can be chosen.
        """
        (x1, y1) = point1 #
        (x2, y2) = point2
        for i in range(4):
            x3, y3 = points[i] # 这是Qt点类的列表吗？还能这么用？
            x4, y4 = points[(i + 1) % 4]
            denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
            nua = (x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)
            nub = (x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)
            if denom == 0:
                # This covers two cases:
                #   nua == nub == 0: Coincident
                #   otherwise: Parallel
                continue
            ua, ub = nua / denom, nub / denom
            if 0 <= ua <= 1 and 0 <= ub <= 1:
                x = x1 + ua * (x2 - x1)
                y = y1 + ua * (y2 - y1)
                m = QtCore.QPoint((x3 + x4) / 2, (y3 + y4) / 2)
                d = labelme.utils.distance(m - QtCore.QPoint(x2, y2))
                yield d, i, (x, y)

    # These two, along with a call to adjustSize are required for the
    # scroll area.
    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        if self.pixmap:
            return self.scale * self.pixmap.size()
        return super(Canvas, self).minimumSizeHint()

    def wheelEvent(self, ev):
        if QT5:
            mods = ev.modifiers()
            delta = ev.angleDelta()
            if QtCore.Qt.ControlModifier == int(mods):
                # with Ctrl/Command key
                # zoom
                self.zoomRequest.emit(delta.y(), ev.pos())
            else:
                # scroll
                self.scrollRequest.emit(delta.x(), QtCore.Qt.Horizontal)
                self.scrollRequest.emit(delta.y(), QtCore.Qt.Vertical)
        else:
            if ev.orientation() == QtCore.Qt.Vertical:
                mods = ev.modifiers()
                if QtCore.Qt.ControlModifier == int(mods):
                    # with Ctrl/Command key
                    self.zoomRequest.emit(ev.delta(), ev.pos())
                else:
                    self.scrollRequest.emit(
                        ev.delta(),
                        QtCore.Qt.Horizontal
                        if (QtCore.Qt.ShiftModifier == int(mods))
                        else QtCore.Qt.Vertical)
            else:
                self.scrollRequest.emit(ev.delta(), QtCore.Qt.Horizontal)
        ev.accept()

    def keyPressEvent(self, ev): # 键盘事件
        key = ev.key()
        if key == QtCore.Qt.Key_Escape and self.current: # 如果按下的是Esc键 并且当前shape有点存在
            self.current = None # 清空current
            self.drawingPolygon.emit(False) # 绘制退出
            self.update() #
        elif key == QtCore.Qt.Key_Return and self.canCloseShape():
            self.finalise()

    def setLastLabel(self, text, flags):
        assert text
        self.shapes[-1].label = text
        self.shapes[-1].flags = flags
        self.shapesBackups.pop()
        self.storeShapes()
        return self.shapes[-1]

    def undoLastLine(self):
        assert self.shapes
        self.current = self.shapes.pop()
        self.current.setOpen()
        if self.createMode in ['polygon', 'linestrip']:
            self.line.points = [self.current[-1], self.current[0]]
        elif self.createMode in ['rectangle', 'line', 'circle']:
            self.current.points = self.current.points[0:1]
        elif self.createMode == 'point':
            self.current = None
        self.drawingPolygon.emit(True)

    def undoLastPoint(self):
        if not self.current or self.current.isClosed():
            return
        self.current.popPoint()
        if len(self.current) > 0:
            self.line[0] = self.current[-1]
        else:
            self.current = None
            self.drawingPolygon.emit(False)
        self.repaint()

    def loadPixmap(self, pixmap):
        self.pixmap = pixmap
        self.shapes = []
        self.repaint()

    def loadShapes(self, shapes, replace=True):
        if replace:
            self.shapes = list(shapes)
        else:
            self.shapes.extend(shapes)
        self.storeShapes()
        self.current = None
        self.hShape = None
        self.hVertex = None
        self.hEdge = None
        self.repaint()

    def setShapeVisible(self, shape, value):
        self.visible[shape] = value
        self.repaint()

    def overrideCursor(self, cursor):
        self.restoreCursor()
        self._cursor = cursor
        QtWidgets.QApplication.setOverrideCursor(cursor)

    def restoreCursor(self):
        QtWidgets.QApplication.restoreOverrideCursor()

    def resetState(self):
        self.restoreCursor()
        self.pixmap = None
        self.shapesBackups = []
        self.update()
