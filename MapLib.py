#!/usr/bin/python
# -*- coding: UTF-8 -*-
from __future__ import print_function  # use python 3 syntax but make it compatible with python 2
from __future__ import division  # ''

import matplotlib.pyplot as plt
from matplotlib import animation
import numpy as np
import time
import os


class Map2D:
    def __init__(self, map_description_file):
        """
        Load and initialize map from file. \

        map_description_file: path to a text file containing map description in the standard format. \
        Example for a 3x3 grid map, with (squared) cells of 400mm side length called mapa0. \
        All free space, i.e., all connections between cells are open, except those on the limits of the map.  
        For more details on the format, see class documentation.

        mapa0.txt content:
        3 3 400
        0 0 0 0 0 0 0
        0 1 1 1 1 1 0
        0 1 1 1 1 1 0
        0 1 1 1 1 1 0
        0 1 1 1 1 1 0
        0 1 1 1 1 1 0
        0 0 0 0 0 0 0      
        
        """
        # params to visualize
        self.mapLineStyle = 'r-'
        self.verbose = False
        self.current_ax = None

        # variables about map params
        self.sizeX = 0
        self.sizeY = 0
        self.sizeCell = 0

        self.connectionMatrix = None
        self.costMatrix = None
        self.currentPath = None

        self.neighbor = np.array([[1, 1, 0, -1, -1, -1, 0, 1],  # row index
                                  [0, 1, 1, 1, 0, -1, -1, -1]])  # column index
        self.sizeXExtended = 0
        self.sizeYExtended = 0

        if self._loadMap(map_description_file):
            print("Map %s loaded ok" % map_description_file)
        else:
            print("Map %s NOT loaded" % map_description_file)

    # from python docs: https://docs.python.org/3/tutorial/classes.html#private-variables
    # “Private” instance variables that cannot be accessed except from inside an object don’t exist in Python. 
    # However, there is a convention that is followed by most Python code: a name prefixed with an underscore \
    # (e.g. _spam) should be treated as a non-public part of the API (whether it is a function, a method or a data member).

    # ############################################################
    # private methods 
    # ############################################################
    def _initConnections(self, init_value=0):
        """
        to initialize the matrix, we set all connections to be closed. 
        When the file with the description is loaded, it will "open" (set to 1) the corresponding ones.
        """
        self.connectionMatrix = np.ones((2 * self.sizeX + 1, 2 * self.sizeY + 1)) * init_value

    def _loadMap(self, mapFileName):
        """ 
        Load map from a txt file (mapFileName) to fill the map params and connectionMatrix. \
        NOTES: \
        \t connectionMatrix is a numpy array \
        \t Function will return False if something went wrong loading the map file.
        """
        try:
            # FILL GLOBAL VARIABLES dimX dimY cellSize
            loadingOk = False
            mapF = open(mapFileName, "r")

            # 1. special case for first line. initialize dimX dimY cellSize
            header = mapF.next()
            tmp = header.split()  # any whitespace string is a separator and empty strings are removed from the result
            if self.verbose:
                print("Header line: %s " % header)
            parsed_header = [int(c) for c in tmp]
            # expected to have three numbers: sizeX sizeY sizeCell_in_mm
            if len(parsed_header) == 3:
                self.sizeX, self.sizeY, self.sizeCell = parsed_header
            else:
                print("Wrong header in map file: %s" % header)
                return False

            # 2.init connectionMatrix
            self._initConnections()

            # 3. load rest of the map connection lines information
            for indx, line in enumerate(mapF):
                # we start loading from the file the "top" row of the map
                current_row = (self.connectionMatrix.shape[1] - 1) - indx
                # Split numbers in the line. Any whitespace string is a separator and empty strings are
                # removed from the result
                tmp = line.split()
                if self.verbose:
                    print("Line for map row %d: %s " % (current_row, line))
                parsed_line = [int(c) for c in tmp]

                if len(parsed_line) == self.connectionMatrix.shape[0] and indx < self.connectionMatrix.shape[1]:
                    self.connectionMatrix[:, current_row] = parsed_line
                elif len(parsed_line):  # don't give errors because of empty lines
                    print("Wrong connectionMatrix (%s) row data: %s" % (self.connectionMatrix.shape(), line))
                    return False
            mapF.close()
            loadingOk = True
        except Exception as e:
            print("ERROR:", e.__doc__)
            print("\t", e.message)
            # raise
            loadingOk = False

        return loadingOk

    def _cell2connCoord(self, cellX, cellY, numNeigh):
        """ 
        Input: 
            cellX, cellY: cell coordinates (cellX, cellY) in the map grid 
            numNeigh: index of one of the cell 8-neighbours

        Output:
            (connX,connY): 2D coordinates (in the connectionMatrix!!) \
            of the connection of the input cell to the input neighbour
        """
        connX = 2 * cellX + 1
        connY = 2 * cellY + 1
        p = [connX, connY]

        result = {
            0: lambda p: [p[0], p[1] + 1],
            1: lambda p: [p[0] + 1, p[1] + 1],
            2: lambda p: [p[0] + 1, p[1]],
            3: lambda p: [p[0] + 1, p[1] - 1],
            4: lambda p: [p[0], p[1] - 1],
            5: lambda p: [p[0] - 1, p[1] - 1],
            6: lambda p: [p[0] - 1, p[1]],
            7: lambda p: [p[0] - 1, p[1] + 1],
        }

        return result[numNeigh](p)

    def _pos2cell(self, x_mm, y_mm):
        """ Convert from robot odometry coordinates (in mm) to cell coordinates """
        # make sure we discretize the result to the closest lower integer value
        x_cell = int(np.floor(x_mm / self.sizeCell))
        y_cell = int(np.floor(y_mm / self.sizeCell))
        return [x_cell, y_cell]

    # ############################################################
    # public methods
    # ############################################################
    def setConnection(self, cellX, cellY, numNeigh):
        """
        open a connection, i.e., we can go straight from cellX,cellY to its neighbour number numNeigh 
        """
        # from coordinates in the grid of cells to coordinates in the connection matrix
        [connX, connY] = self._cell2connCoord(cellX, cellY, numNeigh)
        self.connectionMatrix[connX, connY] = 1  # True

    def deleteConnection(self, cellX, cellY, numNeigh):
        """
        close a connection, i.e., we can NOT go straight from cellX,cellY to its neighbour number numNeigh 
        """
        # from coordinates in the grid of cells to coordinates in the connection matrix
        [connX, connY] = self._cell2connCoord(cellX, cellY, numNeigh)
        self.connectionMatrix[connX, connY] = 0  # False

    def isConnected(self, cellX, cellY, numNeigh):
        """
        returns True if the connnection from cell (x,y) to its neighbour number numNeigh is open.

        The neighbour indexing is considered as follows
        (8-neighbours from cell x,y numbered clock-wise):

        7     0       1    
        6   (x,y)     2
        5     4       3

        """
        [connX, connY] = self._cell2connCoord(cellX, cellY, numNeigh)
        return self.connectionMatrix[connX, connY]

    # aux functions to display (or save image) with robot and map stuff
    def _drawGrid(self):
        """
        aux function to create a grid with map lines
        """
        if not self.current_ax:
            print("Error plotting: do not call this function directly, \
                call drawMap first to create a plot where to draw")
            return False

        plt.rc('grid', linestyle="--", color='gray')
        plt.grid(True)
        plt.tight_layout()

        x_t = range(0, (self.sizeX + 1) * 400, 400)
        y_t = range(0, (self.sizeY + 1) * 400, 400)
        x_labels = [str(n) for n in x_t]
        y_labels = [str(n) for n in y_t]
        plt.xticks(x_t, x_labels)
        plt.yticks(y_t, y_labels)

        # Main rectangle
        X = np.array([0, self.sizeX, self.sizeX, 0, 0]) * self.sizeCell
        Y = np.array([0, 0, self.sizeY, self.sizeY, 0]) * self.sizeCell
        self.current_ax.plot(X, Y, self.mapLineStyle)

        # "vertical" walls
        for i in range(2, 2 * self.sizeX, 2):
            for j in range(1, 2 * self.sizeY, 2):
                if not self.connectionMatrix[i, j]:
                    # paint "right" wall from cell (i-1)/2, (j-1)/2
                    cx = np.floor((i - 1) / 2)
                    cy = np.floor((j - 1) / 2)
                    X = np.array([cx + 1, cx + 1]) * self.sizeCell
                    Y = np.array([cy, cy + 1]) * self.sizeCell
                    self.current_ax.plot(X, Y, self.mapLineStyle)

        # "horizontal" walls
        for j in range(2, 2 * self.sizeY, 2):
            for i in range(1, 2 * self.sizeX, 2):
                if not self.connectionMatrix[i, j]:
                    # paint "top" wall from cell (i-1)/2, (j-1)/2
                    cx = np.floor((i - 1) / 2)
                    cy = np.floor((j - 1) / 2)
                    X = np.array([cx, cx + 1]) * self.sizeCell
                    Y = np.array([cy + 1, cy + 1]) * self.sizeCell
                    self.current_ax.plot(X, Y, self.mapLineStyle)
        plt.axis('equal')

        return True

    # Dibuja robot en location_eje con color (c) y tamano (p/g)
    def _drawRobot(self, loc_x_y_th=[0, 0, 0], robotPlotStyle='b', small=False):
        """
        UPDATES existing plot to include current robot position 
        It expects an existing open figure (probably with the map already on it)

        loc_x_y_th is the position x,y and orientation in mm and radians of the main axis of the robot

        """
        if not self.current_ax:
            print("Error plotting: do not call this function directly, \
                call drawMap first to create a plot where to draw")
            return False

        if small:
            largo, corto, descentre = [80, 50, 5]
        else:
            largo, corto, descentre = [160, 100, 10]

        trasera_dcha = np.array([-largo, -corto, 1])
        trasera_izda = np.array([-largo, corto, 1])
        delantera_dcha = np.array([largo, -corto, 1])
        delantera_izda = np.array([largo, corto, 1])
        frontal_robot = np.array([largo, 0, 1])

        tita = loc_x_y_th[2]
        Hwe = np.array([[np.cos(tita), -np.sin(tita), loc_x_y_th[0]],
                        [np.sin(tita), np.cos(tita), loc_x_y_th[1]],
                        [0, 0, 1]])

        Hec = np.array([[1, 0, descentre],
                        [0, 1, 0],
                        [0, 0, 1]])

        extremos = np.array(
            [trasera_izda, delantera_izda, delantera_dcha, trasera_dcha, trasera_izda, frontal_robot, trasera_dcha])
        robot = np.dot(Hwe, np.dot(Hec, np.transpose(extremos)))

        self.current_ax.plot(robot[0, :], robot[1, :], robotPlotStyle)

        return True

    def drawMapWithRobotLocations(self,
                                  robotPosVectors=[[0, 0, 0], [600, 600, 3.14]],
                                  saveSnapshot=True):
        """ Overloaded version of drawMap to include robot positions """
        return self.drawMap(robotPosVectors=robotPosVectors, saveSnapshot=saveSnapshot)

    def drawMap(self, robotPosVectors=None, saveSnapshot=False):
        """
        Generates a plot with currently loaded map status

        NOTE: 
        if verbose, it displays the plot
        if saveSnapshot: saves a figure as mapstatus_currenttimestamp_FIGNUM.png
        """
        # create a new figure and set it as current axis
        current_fig = plt.figure()
        self.current_ax = current_fig.add_subplot(111)

        self._drawGrid()

        if robotPosVectors:
            for loc in robotPosVectors:
                print("Robot in pos: ", loc)
                self._drawRobot(loc_x_y_th=loc, robotPlotStyle='b--')
            # plot last robot position with solid green line
            self._drawRobot(loc_x_y_th=loc, robotPlotStyle='g-')

        if saveSnapshot:
            ts = str(time.time())
            snapshot_name = "mapstatus_" + ts + "_F" + str(current_fig.number) + ".png"
            print("saving %s " % snapshot_name)
            plt.savefig(snapshot_name)

        if self.verbose:
            current_fig.set_visible(True)
            current_fig.show()
            print("Press ENTER in the plot window to continue ... ")
            current_fig.waitforbuttonpress()
        else:
            current_fig.set_visible(False)

        return current_fig

    def planPath(self, point_ini, point_end):
        """ overloaded call to planPath (x_ini,  y_ini, x_end, y_end) """
        return self.findPath(point_ini[0], point_ini[1],
                             point_end[0], point_end[1])

    # ############################################################
    # METHODS to IMPLEMENT in P4
    # ############################################################

    def getNumberObstacles(self):
        n = 0
        for i in range(0, 2 * self.sizeX + 1):
            for j in range(0, 2 * self.sizeY + 1):
                if self.connectionMatrix[i][j] == 1:
                    n += 1
        return n

    def propagateWavefront(self, grid, origin):
        numberUpdates = 0
        cellsUpdated = []
        for i in range(0, 8):
            x, y = (origin[0] + self.neighbor[0][i], origin[1] + self.neighbor[1][i])
            if 0 <= x < 2 * self.sizeX + 1 and 0 <= y < 2 * self.sizeY + 1:
                updated = False
                if grid[x, y] == -2:
                    grid[x, y] = grid[origin[0], origin[1]] + 1
                    updated = True
                elif grid[x, y] > (grid[origin[0], origin[1]] + 1) and grid[x, y] != -1:
                    grid[x, y] = grid[origin[0], origin[1]] + 1
                    updated = True

                if updated:
                    numberUpdates += 1
                    cellsUpdated.append([x, y])

        return numberUpdates

    def incrementWavefront(self, cells_updated, grid):
        new_wavefront = []
        for cell in cells_updated:
            for i in range(0, 8):
                x, y = (cell[0] + self.neighbor[0][i], cell[1] + self.neighbor[1][i])
                if 0 <= x < 2 * self.sizeX + 1 and 0 <= y < 2 * self.sizeY + 1 and grid[x, y] != -1:
                    if grid[x, y] == grid[cell[0]][cell[1]] + 1:
                        new_wavefront.append((x, y))
        return new_wavefront

    def fillCostMatrix(self, goalCell):
        self.sizeXExtended = 2 * self.sizeX + 1
        self.sizeYExtended = 2 * self.sizeY + 1

        goalX = 2 * goalCell[0] + 1
        goalY = 2 * goalCell[1] + 1
        goal = [goalX, goalY]

        grid = -2 * np.ones((self.sizeXExtended, self.sizeYExtended))
        for i in range(0, self.sizeXExtended):
            for j in range(0, self.sizeYExtended):
                if self.connectionMatrix[i][j] == 0:
                    grid[i][j] = -1

        grid[goal[0]][goal[1]] = 0

        finished = False
        wavefront = [goal]
        while not finished:
            numberUpdates = 0
            for cell in wavefront:
                numberUpdates += self.propagateWavefront(grid, cell)

            if numberUpdates == 0:
                finished = True
            wavefront = self.incrementWavefront(wavefront, grid)
        print(wavefront)

    # NOTE: Make sure self.costMatrix is a 2D numpy array
    # TO-DO
    # """
    # self.costMatrix = ....


    def findPath(self, x_ini, y_ini, x_end, y_end):
        """ 
        x_ini, y_ini, x_end, y_end: integer values that indicate \ 
            the x and y coordinates of the starting (ini) and ending (end) cell

        NOTE: Make sure self.currentPath is a 2D numpy array
        ...  TO-DO  ....
        """
        x_ini = 2 * x_ini + 1
        y_ini = 2 * y_ini + 1

        x_end = 2 * x_end + 1
        y_end = 2 * y_end + 1

        # FAKE sample path: [ [0,0], [0,0], [0,0], ...., [0,0]  ]
        if self.currentPath is None:
            self.currentPath = np.array([x_ini, y_ini])
        else:
            self.currentPath = np.concatenate((self.currentPath, np.array([x_ini, y_ini])))

        if self.costMatrix[x_ini, y_ini] == -1:
            # Never should go into
            return False
        elif x_ini == x_end and y_ini == y_end:
            return True
        else:
            best_step = None
            low_path = 10000000  # If we increase the map we should change this value
            for i in [[0, 1], [0, -1], [1, 0], [-1, 0]]:
                # 4 neighbours
                next_mov_x, next_mov_y = [i[0] + x_ini, i[1] + y_ini]

                if low_path > self.costMatrix[next_mov_x, next_mov_y]:
                    best_step = [next_mov_x, next_mov_y]
                    low_path = self.costMatrix[next_mov_x, next_mov_y]

            for i in [[1, -1], [1, 1], [-1, 1], [-1, -1]]:
                if (self.costMatrix[x_ini + i[0], y_ini] != -1) and (self.costMatrix[x_ini, y_ini + i[1]] != -1):
                    # 8 neighbours
                    next_mov_x, next_mov_y = [i[0] + x_ini, i[1] + y_ini]

                    if low_path > self.costMatrix[next_mov_x, next_mov_y]:
                        best_step = [next_mov_x, next_mov_y]
                        low_path = self.costMatrix[next_mov_x, next_mov_y]

            return self.findPath(best_step[0], best_step[1], x_end, y_end)

    # def replanPath(self, ??):
    # """ TO-DO """