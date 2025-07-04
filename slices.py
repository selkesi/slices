
haveGlutForFonts = False  

import sys, os, math, enum, pprint

try: # PyOpenGL
    from OpenGL.GL import *
    from OpenGL.GLU import *
except:
    print( 'Error: PyOpenGL has not been installed.' )
    sys.exit(0)

try: # GLFW
    import glfw
except:
    print( 'Error: GLFW has not been installed.' )
    sys.exit(0)


if haveGlutForFonts:
    try: # GLUT
      from OpenGL.GLUT import *
    except:
      print( 'Error: Could not import OpenGL.GLUT.  Set haveGlutForFonts = False unless you can install GLUT.' )
      sys.exit(0)


# Globals

windowWidth  = 800
windowHeight = 800
window       = None

allSlices    = []
allTriangles = []

showCurrentSlice = False
labelVerts       = False
labelEdges       = False
labelTris        = False
currentSlice     = 0


# Vertex

class Vertex(object):

    nextID = 0
    
    def __init__( self, coords ):

        self.coords = coords   # [x,y,z] coordinates
        self.nextV  = None     # next vertex in order around the slice

        self.id     = Vertex.nextID
        Vertex.nextID += 1

    def __repr__( self ):
        return 'v%d' % self.id

  
# Slice
#
# Contains a 'verts' list, each item of which is a 3D vertex as [x,y,z]

class Slice(object):

    nextID = 0
    
    def __init__( self, verts ):

        self.verts     = verts  # [ v0, v1, v2, v3, ... ] in RH order around +y axis

        self.id        = Slice.nextID
        Slice.nextID += 1

    def __repr__( self ):
        return 's%d' % self.id

    # Draw this slice
    
    def draw(self):

        glColor3f( 0, 0, 0 );

        # Draw points
        
        # glBegin( GL_POINTS )
        # for v in self.verts:
        #     glVertex3fv( v.coords )
        # glEnd()

        # Draw segments that fade from dark (0,0,0) at tail to light
        # (1,1,1) at head so that direction can been seen.

        glBegin( GL_LINES )
        for v in self.verts:
            glColor3f( 0,0,0 )
            glVertex3fv( v.coords )
            glColor3f( 1,1,1 )
            glVertex3fv( v.nextV.coords )
        glEnd()



# Triangle

class Triangle(object):

    nextID = 0
    
    def __init__( self, verts ):

        self.verts = verts # [ v0, v1, v2 ] is CCW order as seen from outside the object
        
        self.norm  = normalize( crossProduct( subtract( verts[1].coords, verts[0].coords ), # outward-pointing normal
                                              subtract( verts[2].coords, verts[0].coords ) ) )

        self.id    = Triangle.nextID
        Triangle.nextID += 1

    def __repr__( self ):
        return 't%d' % self.id

class Dir(enum.Enum):
    PREV_ROW = 1
    PREV_COL = 2


def buildTriangles( slice0, slice1 ):

    # Find the closest pair of vertices (one from each slice) to start with.

    def findClosestVertices(slice0, slice1):
        # sort by x coordinate
        slice0_sorted = sorted(slice0.verts, key=lambda v: v.coords[0])
        slice1_sorted = sorted(slice1.verts, key=lambda v: v.coords[0])
        min_distance = float('inf')
        closest_pair = None
        # sliding counter
        j_start = 0 
        # for each vertex in the first slice,
        for v0 in slice0_sorted:
            x0 = v0.coords[0] 
            while j_start < len(slice1_sorted) and slice1_sorted[j_start].coords[0] < x0 - min_distance:
                j_start += 1
            # iterate through second slice and check distances
            for j in range(j_start, len(slice1_sorted)):
                v1 = slice1_sorted[j]
                if v1.coords[0] > x0 + min_distance:
                    break
                diff = subtract(v0.coords, v1.coords)
                distance_sq = dotProduct(diff, diff)
                if distance_sq < min_distance:
                    min_distance = distance_sq
                    closest_pair = (v0, v1)
                if min_distance == 0:
                    return closest_pair

        return closest_pair

    # minV0    # closest vertex on top slice
    # minV1    # closest vertex on bottom slice
    minV0, minV1 = findClosestVertices(slice0, slice1)

    start0 = slice0.verts.index(minV0)
    start1 = slice1.verts.index(minV1)

    verts0 = slice0.verts[start0:] + slice0.verts[:start0]
    verts1 = slice1.verts[start1:] + slice1.verts[:start1]

    verts0.append(verts0[0])
    verts1.append(verts1[0])

    minArea = [[0] * len(verts0) for _ in range(len(verts1))]
    minDir  = [[None] * len(verts0) for _ in range(len(verts1))]


    minArea[0][0] = 0  # Starting edge has zero area

    for c in range(1, len(verts0)):
        minArea[0][c] = minArea[0][c - 1] + triangleArea(verts1[0].coords, verts0[c - 1].coords, verts0[c].coords)
        minDir[0][c] = Dir.PREV_COL
    
    for r in range(1, len(verts1)):
        minArea[r][0] = minArea[r - 1][0] + triangleArea(verts1[r - 1].coords, verts1[r].coords, verts0[0].coords)
        minDir[r][0] = Dir.PREV_ROW

    for r in range(1, len(verts1)):
        for c in range(1, len(verts0)):
            area_from_row = minArea[r - 1][c] + triangleArea(verts1[r - 1].coords, verts1[r].coords, verts0[c].coords)
            area_from_col = minArea[r][c - 1] + triangleArea(verts1[r].coords, verts0[c - 1].coords, verts0[c].coords)
            if minArea[r-1][c] < minArea[r][c-1]:
                minArea[r][c] = area_from_row
                minDir[r][c] = Dir.PREV_ROW
            else:
                minArea[r][c] = area_from_col
                minDir[r][c] = Dir.PREV_COL

    # Debugging

    # print minDir and minArea arrays in readable format
    # print("               ", end="")
    # for c in range(len(verts0)):
    #     print(f"  {c:4}", end="")
    # print()
    # for r in range(len(verts1)):
    #     print(f"{r:4}", end="   ")
    #     for c in range(len(verts0)):
    #         print(f"{minArea[r][c]:6.0f}", end=" ")
    #         if minDir[r][c] == Dir.PREV_ROW:
    #             print("|", end=" ")
    #         elif minDir[r][c] == Dir.PREV_COL:
    #             print("-", end=" ")
    #         else:
    #             print(" ", end=" ")
    #     print()

    # Walk backward through the 'minDir' array to build triangulation.

    triangles = []
    r, c = len(verts1) - 1, len(verts0) - 1

    # iterate backwards through array and append triangles
    while r > 0 or c > 0:
        if minDir[r][c] == Dir.PREV_ROW:
            triangles.append(Triangle([verts1[r-1], verts1[r], verts0[c]]))
            r -= 1
        elif minDir[r][c] == Dir.PREV_COL:
            triangles.append(Triangle([verts1[r], verts0[c-1], verts0[c]]))
            c -= 1

    return triangles


# Set up the display and draw the current image

fovy  = 6     # field-of-view
fNear = 10    # near plane
fFar  = 10000 # far plane

eye    = [100,100,1000]
lookat = [0,0,0]
updir  = [0,1,0]

rotationAngle = None
rotationAxis  = None
fovyDelta     = None


def display( wait=False ):

    # Handle any events that have occurred

    glfw.poll_events()

    # Set up window

    glClearColor( 1,1,1,0 )
    glClear( GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT );
    glEnable( GL_DEPTH_TEST )
    glPolygonMode( GL_FRONT_AND_BACK, GL_FILL )

    # Apply zoom to fovy

    glMatrixMode( GL_PROJECTION )
    glLoadIdentity()

    if fovyDelta is not None:
        zoomedFovy = fovy + fovyDelta
    else:
        zoomedFovy = fovy

    gluPerspective( zoomedFovy, float(windowWidth) / float(windowHeight), fNear, fFar );

    # Apply rotation to eye position

    if rotationAngle is None:
        rotatedEye = eye
        rotatedUp  = updir
    else:
        rotatedEye = rotateVector( eye,   rotationAngle, rotationAxis )
        rotatedUp  = rotateVector( updir, rotationAngle, rotationAxis )

    glMatrixMode( GL_MODELVIEW )
    glLoadIdentity()

    gluLookAt( rotatedEye[0], rotatedEye[1], rotatedEye[2],
	       lookat[0],     lookat[1],     lookat[2],
	       rotatedUp[0],  rotatedUp[1],  rotatedUp[2] );

    # Draw slices

    if showCurrentSlice:
        slicesToDraw = [ allSlices[currentSlice], allSlices[currentSlice+1] ]
    else:
        slicesToDraw = allSlices

    if allTriangles == []:
        for slice in slicesToDraw:
            slice.draw() # draws the EDGES of each slice

    # Set up lighting for triangles

    lightDir = add( scalarMult( 5, normalize( rotatedEye ) ), # light is above and right of viewer
                    add( normalize( rotatedUp ), 
                         normalize( crossProduct( rotatedUp, rotatedEye ) ) ) )

    glLightfv( GL_LIGHT0, GL_POSITION, lightDir + [0.0] )

    glLightfv( GL_LIGHT0, GL_AMBIENT,  [ 0.2, 0.2, 0.2, 0.0 ] )
    glLightfv( GL_LIGHT0, GL_DIFFUSE,  [ 1.0, 1.0, 1.0, 0.0 ] )
    glLightfv( GL_LIGHT0, GL_SPECULAR, [ 1.0, 1.0, 1.0, 0.0 ] )

    glEnable( GL_LIGHT0 )

    glLightModeli( GL_LIGHT_MODEL_TWO_SIDE, GL_TRUE )

    # Draw triangles

    glEnable( GL_LIGHTING )
    
    glBegin( GL_TRIANGLES )
    for tri in allTriangles:
        glNormal3fv( tri.norm )
        glVertex3fv( tri.verts[0].coords )
        glVertex3fv( tri.verts[1].coords )
        glVertex3fv( tri.verts[2].coords )
    glEnd()

    glDisable( GL_LIGHTING )

    # Draw axes (x=red, y=green, z=blue)

    glLineWidth( 3.0 )
    glBegin( GL_LINES )

    l = 10 # axis length

    glColor3fv( [1,0,0] )  # x
    glVertex3fv( [0,0,0] )
    glVertex3fv( [l,0,0] )

    glColor3fv( [0,1,0] )  # y
    glVertex3fv( [0,0,0] )
    glVertex3fv( [0,l,0] )

    glColor3fv( [0,0,1] )  # z
    glVertex3fv( [0,0,0] )
    glVertex3fv( [0,0,l] )

    glEnd()
    glLineWidth( 1.0 )

    # Draw labels

    glDisable( GL_DEPTH_TEST )

    if labelVerts:
        glColor3f(0,0,0)
        for slice in slicesToDraw:
            for vert in slice.verts:
                drawText( vert.coords, repr(vert) )
    
    if labelEdges:
        glColor3f(0,0,0)
        for slice in slicesToDraw:
            for vert in slice.verts:
                drawText( scalarMult( 0.5, add( vert.coords, vert.nextV.coords ) ), ('%s-%s' % (repr(vert),repr(vert.nextV))) )
    
    if labelTris:
        glColor3f(0,0,0)
        for tri in allTriangles:
            drawText( scalarMult( 0.3333, add( tri.verts[0].coords, add( tri.verts[1].coords, tri.verts[2].coords ) ) ), repr(tri) )
    
    # Show window

    glfw.swap_buffers( window )

    

def drawText( coords, text ):

    if haveGlutForFonts:
        glRasterPos3fv( coords )
        for ch in text:
            glutBitmapCharacter( GLUT_BITMAP_8_BY_13, ord(ch) )



# Handle keyboard input

def keyCallback( window, key, scancode, action, mods ):

    global currentSlice, showCurrentSlice, allTriangles, labelVerts, labelEdges, labelTris
    
    if action == glfw.PRESS:
    
        if key == glfw.KEY_ESCAPE: # quit upon ESC
            sys.exit(0)

        elif key == ord('C'): # compute min-area triangulation

            if showCurrentSlice:
                allTriangles = buildTriangles( allSlices[currentSlice], allSlices[currentSlice+1] )
            else:
                allTriangles = []
                for i in range(len(allSlices)-1):
                    sys.stdout.write( '\r%d left ' % (len(allSlices)-1-i) )
                    sys.stdout.flush();
                    allTriangles += buildTriangles( allSlices[i], allSlices[i+1] )
                sys.stdout.write( '\r          \n' )
            
        elif key == ord('S'): # show current slice
            showCurrentSlice = not showCurrentSlice

        elif key == ord(','): # current slice moves up
            if currentSlice > 0:
                currentSlice -= 1
            
        elif key == ord('.'): # current slice moves down
            if currentSlice < len(allSlices)-2:
                currentSlice += 1

        elif key == ord('V'): # toggle vertex labels
            labelVerts = not labelVerts

        elif key == ord('E'): # toggle edge labels
            labelEdges = not labelEdges

        elif key == ord('T'): # toggle triangle labels
            labelTris = not labelTris

        elif key == ord('/'):

            print( 'keys: c - compute min-area triangulation' )
            print( '      s - toggle current slice' )
            print( '      < - current slice moves up' )
            print( '      > - current slice moves down' )
            print( '      v - toggle vertex labels' )
            print( '      e - toggle edge labels' )
            print( '      t - toggle triangle labels' )
            print( '' )
            print( 'mouse: drag left button          - rotate' )
            print( '       drag right button up/down - zoom' )



# Handle window reshape

def windowReshapeCallback( window, newWidth, newHeight ):

    global windowWidth, windowHeight

    windowWidth  = newWidth
    windowHeight = newHeight



# Handle mouse click/release

initX  = 0
initY  = 0
button = None

def mouseButtonCallback( window, btn, action, keyModifiers ):

    global button, initX, initY, eye, updir, fovy, rotationAngle, rotationAxis, fovyDelta

    if action == glfw.PRESS:

        button = btn
        initX, initY = glfw.get_cursor_pos( window ) # store mouse position

        rotationAngle = 0
        rotationAxis  = [1,0,0]

    elif action == glfw.RELEASE:

        if rotationAngle is not None:
            eye   = rotateVector( eye, rotationAngle, rotationAxis )
            updir = rotateVector( updir, rotationAngle, rotationAxis )

        if fovyDelta is not None:
            fovy = fovy + fovyDelta

        button        = None
        rotationAngle = None
        fovyDelta     = None

    

# Handle mouse motion.  We don't want to transform the image and
# redraw with each tiny mouse movement.  Instead, just record the fact
# that the mouse moved.  After events are processed in
# glfw.wait_events(), check whether the mouse moved and, if so, act on
# it.


mousePositionChanged = False

def mouseMovementCallback( window, x, y ):

  global mousePositionChanged

  if button is not None: # button is held down
      mousePositionChanged = True



def actOnMouseMovement( window, button, x, y ):

    global currentImage, rotationAngle, rotationAxis, fovyDelta

    if button == glfw.MOUSE_BUTTON_LEFT:

        # rotate viewpoint

        # Get initial vector from (0,0,0) to mouse
      
        x0 =   (initX - float(windowWidth)/2.0)  / (float(windowWidth)/2.0)
        y0 = - (initY - float(windowHeight)/2.0) / (float(windowHeight)/2.0)

        dSquared = x0*x0 + y0*y0
        if dSquared > 1:
            d = math.sqrt(dSquared)
            x0 /= d
            y0 /= d
            dSquared = 1

        z0 = math.sqrt( 1 - dSquared )

        # Get current vector from (0,0,0) to mouse
        
        x1 =   (x - float(windowWidth)/2.0)  / (float(windowWidth)/2.0)
        y1 = - (y - float(windowHeight)/2.0) / (float(windowHeight)/2.0)

        dSquared = x1*x1 + y1*y1
        if dSquared > 1:
            d = math.sqrt(dSquared)
            x1 /= d
            y1 /= d
            dSquared = 1

        z1 = math.sqrt( 1 - dSquared )

        # Find rotation angle and axis (in coordinate system aligned with window x and y)

        angleCos = x0*x1 + y0*y1 + z0*z1

        if angleCos > 1:
            angleCos = 1
        elif angleCos < -1:
            angleCos = -1

        rotationAngle = math.acos( angleCos )

        if abs(rotationAngle) < 0.0001:
            rotationAngle = 0
            rotationAxis = [ 1,0,0 ]
        else:
            rotationAxis = crossProduct( [x0,y0,z0], [x1,y1,z1] )
            d = math.sqrt( rotationAxis[0]*rotationAxis[0] + rotationAxis[1]*rotationAxis[1] + rotationAxis[2]*rotationAxis[2] )
            rotationAxis = [ rotationAxis[0]/d, rotationAxis[1]/d, rotationAxis[2]/d ]

        # Move rotation axis into world coordinate system

        eyeZ = normalize( [ eye[0]-lookat[0], eye[1]-lookat[1], eye[2]-lookat[2] ] )
        eyeX = normalize( crossProduct( eyeZ, updir ) )
        eyeY = normalize( crossProduct( eyeZ, eyeX ) )

        rotationAxis = [ rotationAxis[0] * eyeX[0] + rotationAxis[1] * eyeY[0] + rotationAxis[2] * eyeZ[0],
                         rotationAxis[0] * eyeX[1] + rotationAxis[1] * eyeY[1] + rotationAxis[2] * eyeZ[1],
                         rotationAxis[0] * eyeX[2] + rotationAxis[1] * eyeY[2] + rotationAxis[2] * eyeZ[2] ]

    elif button == glfw.MOUSE_BUTTON_RIGHT:

        # zoom viewpoint

        fovyDelta = (initY - y) / float(windowHeight) * fovy



# Some vector functions (to avoid having to install NumPy)


def add( v0, v1 ):

    return [ v0[0]+v1[0], v0[1]+v1[1], v0[2]+v1[2] ]


def subtract( v0, v1 ):

    return [ v0[0]-v1[0], v0[1]-v1[1], v0[2]-v1[2] ]


def scalarMult( k, v ):

    return [ k*v[0], k*v[1], k*v[2] ]

              
def dotProduct( v0, v1 ):

    return v0[0]*v1[0] + v0[1]*v1[1] + v0[2]*v1[2]


def crossProduct( v0, v1 ):

    return [ v0[1]*v1[2] - v0[2]*v1[1], v0[2]*v1[0] - v0[0]*v1[2], v0[0]*v1[1] - v0[1]*v1[0] ]


def length( v ):

    return math.sqrt( v[0]*v[0] + v[1]*v[1] + v[2]*v[2] )


def normalize( v ):

    d = length( v )

    if d > 0.0001:
        return [ v[0]/d, v[1]/d, v[2]/d ]
    else:
        return v


def triangleArea( v0, v1, v2 ):

    return 0.5 * length( crossProduct( subtract( v1, v0 ), subtract( v2, v0 ) ) )


def rotateVector( v, angle, axis ): # rotate v by angle about axis (axis must be unit length)

    cosAngle = math.cos(angle)
    sinAngle = math.sin(angle)

    cross = crossProduct( axis, v )
    dot   = dotProduct( axis, v ) * (1 - cosAngle)


    return [ v[0] * cosAngle + cross[0] * sinAngle + axis[0] * dot,
             v[1] * cosAngle + cross[1] * sinAngle + axis[1] * dot,
             v[2] * cosAngle + cross[2] * sinAngle + axis[2] * dot ]



# Read slices from a file
# Each 'pointA-B' above is 'x y z' separated by spaces.

def readSlices( f ):

    lines = f.readlines()

    numSlices = int(lines[0])
    slices = []
    lineNum = 1

    for i in range(numSlices):

        numPoints = int(lines[lineNum])
        lineNum += 1

        slice = Slice( [ Vertex( [ float(n) for n in line.split() ] )
                         for line in lines[lineNum:lineNum+numPoints] ] )

        for v0,v1 in zip( slice.verts, slice.verts[1:] + [slice.verts[0]] ):
            v0.nextV = v1

        slices.append( slice )
        lineNum += numPoints

    slices.reverse() # so that first slice is on top

    return slices


    
# Initialize GLFW and run the main event loop

def main():

    global window, allSlices, mousePositionChanged
    
    # Check command-line args

    if len(sys.argv) < 2:
        print( 'Usage: %s filename' % sys.argv[0] )
        sys.exit(1)

    args = sys.argv[1:]
    while len(args) > 1:
        # if args[0] == '-x':
        #     pass
        args = args[1:]

    # Set up window
  
    if not glfw.init():
        print( 'Error: GLFW failed to initialize' )
        sys.exit(1)

    if haveGlutForFonts:
        glutInit()

    window = glfw.create_window( windowWidth, windowHeight, "3D Meshing", None, None )

    if not window:
        glfw.terminate()
        print( 'Error: GLFW failed to create a window' )
        sys.exit(1)

    glfw.make_context_current( window )
    glfw.swap_interval( 1 )
    glfw.set_key_callback( window, keyCallback )
    glfw.set_window_size_callback( window, windowReshapeCallback )
    glfw.set_mouse_button_callback( window, mouseButtonCallback )
    glfw.set_cursor_pos_callback( window, mouseMovementCallback )

    # Read the triangles.

    with open( args[0], 'rb' ) as f:
        allSlices = readSlices( f )

    print( 'Read %d slices' % len(allSlices) )

    if len(allSlices) < 2:
        return

    # Main event loop

    display( window )

    while not glfw.window_should_close( window ):

        glfw.wait_events()

        if mousePositionChanged:
          currentX, currentY = glfw.get_cursor_pos( window )
          actOnMouseMovement( window, button, currentX, currentY )
          mousePositionChanged = False
          
        display( window )

    glfw.destroy_window( window )
    glfw.terminate()
    


if __name__ == '__main__':
    main()
