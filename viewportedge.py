'''
Contains class for managing viewport manifestation of edges.
'''

from math import sqrt

def adjust_point(p1, box, p2):
    '''
    Moves p1 along the line p1<->p2 to be on an edge of box

    Args:
    * p1: (x:int, y:int)
    * box: (x:int, y:int, w:int, h:int)
    * p2: (x2:int, y2:int)

    Returns:
    (x:int, y:int), new version of p1
    '''
    # fn for line <--p1--p2-->
    rise = p2[1] - p1[1]
    run  = p2[0] - p1[0]
    # remember, y - y1 = m(x - x1), m = rise/run
    y = lambda x: int( rise*(x - p1[0])/run  + p1[1] )
    x = lambda y: int(  run*(y - p1[1])/rise + p1[0] )
    # coords of side wall and top/bot of box facing p2
    relevant_x = box[0] if run < 0 else box[0] + box[2]
    relevant_y = box[1] if rise < 0 else box[1] + box[3]
    # bail early if edge is vertical or horizontal
    if run == 0:
        return p1[0], relevant_y
    if rise == 0:
        return relevant_x, p1[1]
    # see if the x-coord of the relevant side wall of the wall gives
    # us a valid y-value. if so, return it
    wall_y = y(relevant_x)
    if box[1] <= wall_y <= box[1] + box[3]:
        return (relevant_x, wall_y)
    # if we get here, we know the intersection is on the top or bottom
    return x(relevant_y), relevant_y

def card_box(card):
    '''
    return bounding box of card as (x, y, w, h)
    card is a model.Card
    '''
    return card.x, card.y, card.w, card.h

def box_center(box):
    '''
    center point of box in tuple format, like above fn
    '''
    return (box[0] + box[2]/2, box[1] + box[3]/2)

class ViewportEdge(object):
    '''
    Class for displaying edges

    Handles modifying/redrawing of the lines between cards,
    and for changing their endpoints.

    Members:
    * edge: model.Edge object
    * viewport: GPViewport self belongs to
    * canvas: shortcut to viewport canvas
    * itemid: int handle to item on canvas
    * orig: ViewportCard or None
    * dest: ViewportCard or None
    * orig_callback: int callback handle for geometry callback on orig card
    * dest_callback: as above, s/orig/dest/g
    * coords = [[int]], list of endpoints (post-adjustment)
    * dragging_end = when dragging, and index into coords, else None
    * highlighted_card = when dragging, the card we're highlighting (property)
    '''
    def __init__(self, viewport, gpfile, edge, orig, dest):
        '''
        Arguments:
        * viewport: GPViewport this edge lives in
        * gpfile: GPFile, needed for committing
        * edge: model.Edge that we will be managing.
        '''
        # store all the arguments
        self.edge = edge
        self.viewport = viewport
        self.canvas = viewport.canvas
        self.gpfile = gpfile
        # draw self
        self.reset_coords()
        self.itemid = self.canvas.create_line(
            #0, 0, 100, 0, 100, 100, 200, 100,
            # have to unpack self.get_coords as first args, not last
            *(self.get_coords()),
            arrow='last',
            smooth='raw',
            width=6,
            fill='blue',
            activefill='#6060ff'
        )
        self.canvas.tag_bind(self.itemid, "<Button-1>", self.click)
        self.canvas.tag_bind(self.itemid, "<B1-Motion>", self.mousemove)
        self.canvas.tag_bind(self.itemid, "<ButtonRelease-1>", self.mouseup)
        # set up state
        self.orig_callback = self.dest_callback = None
        self.orig = orig
        self.dest = dest
        # drag state
        self.dragging_end = None # or 0 or 1
        self._highlighted_card = None

    def refresh(self):
        self.canvas.coords(self.itemid, *self.get_coords())

    def reset_coords(self):
        '''
        Set self.coords based on current cards. Only call when orig and
        dest are valid.

        Calculates from the position of self.edge.orig/dest,
        and at some point from the mouse position I guess.
        Straight line between the centers of orig and dest.
        '''
        # watch out for loss of sync between viewport cards and model card
        # also, this will have to be rewritten at some point so any
        # endpoint can be mouse-driven rather than card-driven
        orig = self.edge.orig
        dest = self.edge.dest
        start_point = (orig.x + orig.w/2, orig.y + orig.h/2)
        end_point = (dest.x + dest.w/2, dest.y + dest.h/2)
        #adjust both points to be on edges of cards
        start_point = adjust_point(start_point, card_box(orig), end_point)
        end_point = adjust_point(end_point, card_box(dest), start_point)
        self.coords = [start_point, end_point]

    def get_coords(self):
        "return self.coords in a flattened list"
        return self.coords[0][0], self.coords[0][1], self.coords[1][0], self.coords[1][1]

    def geometry_callback(self, card, x, y, w, h):
        "For passing to ViewportCard slots"
        # we know here that both ends are card-based, no mouse and no loose ends
        box = (x, y, w, h)
        point = (x + w/2, y + h/2) # point in middle of whatever card moved
        # we have to adjust both points, the moved point by the passed box and
        # the other point by the stored box
        if card is self.orig:
            self.coords[0] = adjust_point(point, box, self.coords[1])
            otherbox = card_box(self.dest.card)
            self.coords[1] = adjust_point(box_center(otherbox), otherbox, point)
        elif card is self.dest:
            self.coords[1] = adjust_point(point, box, self.coords[0])
            otherbox = card_box(self.orig.card)
            self.coords[0] = adjust_point(box_center(otherbox), otherbox, point)
        else:
            raise 'Card must be either orig or dest.'
        # adjust both ends
        self.refresh()

    def click(self, event):
        '''
        Determine which end of the edge was clicked on
        '''
        # event coords are window coords, not canvas coords
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        start_x, start_y = self.coords[0]
        end_x, end_y = self.coords[1]
        to_orig = sqrt((start_x - x)**2 + (start_y - y)**2)
        to_dest = sqrt((end_x - x)**2 + (end_y - y)**2)
        #print locals()
        if to_orig < to_dest:
            self.dragging_end = 0
        elif to_dest < to_orig:
            self.dragging_end = 1
        else:
            print 'seriously?'

    def mousemove(self, event):
        '''
        Update dragging_end based on mousemove. Notify Viewport.
        Later, highlight card.
        '''
#        print 'mousemove', event.x, event.y, self.dragging_end
        if self.dragging_end is not None:
            self.coords[self.dragging_end] = (
                self.canvas.canvasx(event.x),
                self.canvas.canvasy(event.y)
            )
            # adjust other endpoint
            non_dragging_end = int(not self.dragging_end)
            non_drag_box = card_box([self.orig, self.dest][non_dragging_end].card)
            self.coords[non_dragging_end] = adjust_point(
                box_center(non_drag_box),
                non_drag_box,
                self.coords[self.dragging_end]
            )
            self.refresh()
            # check out card on other end
            #print self.viewport.card_collision(self.coords[self.dragging_end])
            self.highlighted_card = self.viewport.card_collision(self.coords[self.dragging_end])

    def mouseup(self, event):
        '''
        Choose card to land on. reset coords
        '''
#        print 'mouseup'
        if self.dragging_end is not None:
            # set new end
            # TODO: prevent edge with same card at both ends.
            card = self.viewport.card_collision(self.coords[self.dragging_end])
            if card is not None:
                if self.dragging_end == 0:
                    self.orig = card
                else:
                    self.dest = card
            # update graphics
            self.reset_coords()
            self.refresh()
            self.dragging_end = None
            self.highlighted_card = None

    def get_highlighted_card(self):
        return self._highlighted_card
    def set_highlighted_card(self, new):
        if new is not self._highlighted_card:
            if self._highlighted_card is not None:
                self._highlighted_card.unhighlight()
            if new is not None:
                new.highlight()
            self._highlighted_card = new
        # else, no-op
    highlighted_card = property(get_highlighted_card, set_highlighted_card)

    def get_orig(self):
        return self._orig
    def set_orig(self, orig):
        if self.orig_callback:
            self.orig.remove_signal(self.orig_callback)
        self._orig = orig
        if orig:
            self.orig_callback = orig.add_signal(self.geometry_callback)
            self.edge.orig = orig.card
    orig = property(get_orig, set_orig)

    def get_dest(self):
        return self._dest
    def set_dest(self, dest):
        if self.dest_callback:
            self.dest.remove_signal(self.dest_callback)
        self._dest = dest
        if dest:
            self.dest_callback = dest.add_signal(self.geometry_callback)
            self.edge.dest = dest.card
    dest = property(get_dest, set_dest)
