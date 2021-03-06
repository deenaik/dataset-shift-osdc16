"""Interactive plot to illustrate the phenomenon of covariate shift.
That is, p(x,y) differs from training to testing phase. The interactive plot allows you
to specify p(x) via a probability tabels while p(y|x) remains fixed.
You can see that underspecified discriminative models are not immune to covariate shift.

Use the ``bokeh serve`` command to run the interactive plot:

    bokeh serve bokeh_checkerboard.py

at your command prompt. Then navigate to the URL

    http://localhost:5006/bokeh_checkerboard

in your browser.
"""

import numpy as np
from collections import OrderedDict
from os.path import join
from os.path import dirname

from bokeh.models.widgets import Button
from bokeh.layouts import widgetbox
from bokeh.layouts import row, column
from bokeh.plotting import figure, curdoc
from bokeh.models.widgets import Slider
from bokeh.models.widgets import Select
from bokeh.models import Spacer
from bokeh.models.widgets import Div
from bokeh.palettes import (Blues9, BrBG9, BuGn9, BuPu9, GnBu9, Greens9,
                            Greys9, OrRd9, Oranges9, PRGn9, PiYG9, PuBu9,
                            PuBuGn9, PuOr9, PuRd9, Purples9, RdBu9, RdGy9,
                            RdPu9, RdYlBu9, RdYlGn9, Reds9, Spectral9, YlGn9,
                            YlGnBu9, YlOrBr9, YlOrRd9, Inferno9, Magma9,
                            Plasma9, Viridis9, Accent8, Dark2_8, Paired9,
                            Pastel1_9, Pastel2_8, Set1_9, Set2_8, Set3_9)

from checkerboard import View
from checkerboard import Table
from checkerboard import Controller
from checkerboard import Model


PALETTE = "Spectral9"
IMAGE_ALPHA = 210
FILL_ALPHA = 0.9
LINE_ALPHA = 0.8
standard_palettes = OrderedDict([("Blues9", Blues9), ("BrBG9", BrBG9),
                                 ("BuGn9", BuGn9), ("BuPu9", BuPu9),
                                 ("GnBu9", GnBu9), ("Greens9", Greens9),
                                 ("Greys9", Greys9), ("OrRd9", OrRd9),
                                 ("Oranges9", Oranges9), ("PRGn9", PRGn9),
                                 ("PiYG9", PiYG9), ("PuBu9", PuBu9),
                                 ("PuBuGn9", PuBuGn9), ("PuOr9", PuOr9),
                                 ("PuRd9", PuRd9), ("Purples9", Purples9),
                                 ("RdBu9", RdBu9), ("RdGy9", RdGy9),
                                 ("RdPu9", RdPu9), ("RdYlBu9", RdYlBu9),
                                 ("RdYlGn9", RdYlGn9), ("Reds9", Reds9),
                                 ("Spectral9", Spectral9), ("YlGn9", YlGn9),
                                 ("YlGnBu9", YlGnBu9), ("YlOrBr9", YlOrBr9),
                                 ("YlOrRd9", YlOrRd9), ("Inferno9", Inferno9),
                                 ("Magma9", Magma9), ("Plasma9", Plasma9),
                                 ("Viridis9", Viridis9), ("Accent8", Accent8),
                                 ("Dark2_8", Dark2_8), ("Paired9", Paired9),
                                 ("Pastel1_9", Pastel1_9),
                                 ("Pastel2_8", Pastel2_8), ("Set1_9", Set1_9),
                                 ("Set2_8", Set2_8), ("Set3_9", Set3_9)])

DEFAULT_SIZE = 10  # Default size of circles
KERNELS = ['linear', 'rbf']
INIT_ACTIVE_KERNEL = 'linear'
REWEIGHTINGS = list(Model.REWEIGHTING)
INIT_ACTIVE_REWEIGHTING = Model.REWEIGHTING.NONE


def get_label_colors(palette_name):
    p = standard_palettes[palette_name]
    return p[-1], p[0]


def template_title(dist, err):
    return '{} Distribution        Err: {}'.format(dist.title(), err)


def hex_to_rgb(value):
    value = value.lstrip('#')
    lv = len(value)
    return tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))


class RGBAColorMapper(object):
    """Maps floating point values to rgb values over a palette

    @author: Christine Doig
    """

    def __init__(self, low, high, palette):
        self.range = np.linspace(low, high, len(palette))
        self.r, self.g, self.b = list(zip(*[hex_to_rgb(i) for i in palette]))

    def color(self, data, alpha=255):
        """Maps your data values to the pallette with linear interpolation"""

        red = np.interp(data, self.range, self.r)
        blue = np.interp(data, self.range, self.b)
        green = np.interp(data, self.range, self.g)
        # Style plot to return a grey color when value is 'nan'
        red[np.isnan(red)] = 240
        blue[np.isnan(blue)] = 240
        green[np.isnan(green)] = 240
        colors = np.dstack([red.astype(np.uint8),
                          green.astype(np.uint8),
                          blue.astype(np.uint8),
                          np.full_like(data, alpha, dtype=np.uint8)])
        return colors.view(dtype=np.uint32).reshape(data.shape)


class BokehView(View):

    def __init__(self, controller):
        super(BokehView, self).__init__(controller)

        # define elements
        self.gen_data_button = Button(label="Generate Data", button_type="success")
        self.kernel_select = Select(title='Kernel',
                                    options=KERNELS,
                                    value=INIT_ACTIVE_KERNEL)
        self.reweighting_select = Select(title='Reweighting',
                                         options=REWEIGHTINGS,
                                         value=INIT_ACTIVE_REWEIGHTING)
        self.classify_button = Button(label="Classify", button_type="success")
        self.train_table = BokehTable([[0.4, 0.1], [0.4, 0.1]])
        self.test_table = BokehTable([[0.4, 0.4], [0.1, 0.1]])
        self.train_fig = figure(plot_height=400, plot_width=400,
                                title=template_title('Train', '-'), tools='',
                                x_range=[0, 100], y_range=[-50, 5])
        self.test_fig = figure(plot_height=400, plot_width=400,
                               title=template_title('test', '-'), tools='',
                               x_range=[0, 100], y_range=[-50, 50])

        # wire callbacks
        self.gen_data_button.on_click(controller.generate_data)
        self._kernel = INIT_ACTIVE_KERNEL
        self.kernel_select.on_change('value', self._update_kernel)
        self._reweighting = INIT_ACTIVE_REWEIGHTING
        self.reweighting_select.on_change('value', self._update_reweighting)
        self.classify_button.on_click(self._classify_callback)

        desc = Div(text=open(join(dirname(__file__), "description.html")).read(), width=1024)

        # set layout
        inputs = widgetbox(self.kernel_select,
                           self.reweighting_select,
                           self.gen_data_button,
                           self.classify_button)
        layout = column(row(desc),
                        row(column(row(inputs)), column(row(self.train_fig, self.test_fig),
                                                        row(self.train_table.get_layout_element(),
                                                            Spacer(width=100, height=100),
                                                            self.test_table.get_layout_element()))))
        self.layout = layout

    def _classify_callback(self):
        self.controller.classify(kernel=str(self._kernel))

    def _update_kernel(self, attr, old, new_kernel):
        self._kernel = new_kernel

    def _update_reweighting(self, attr, old, new_reweighting):
        self._reweighting = new_reweighting
        self.controller.reweight(weight=self._reweighting)

    def run(self):
        # set layout and off we go
        curdoc().add_root(self.layout)
        print('added the root')
        curdoc().title = "Checkerboard"
        print('done')

    def update(self, model):
        pos_c, neg_c = get_label_colors(PALETTE)
        color_code = lambda arr: np.where(arr == 1, pos_c, neg_c)

        self.train_fig = figure(plot_height=400, plot_width=400,
                                title=template_title('train', model.trainerr), tools='',
                                x_range=[0, 100], y_range=[-50, 50])
        self.test_fig = figure(plot_height=400, plot_width=400,
                               title=template_title('test', model.testerr), tools='',
                               x_range=[0, 100], y_range=[-50, 50])

        if model.surface is not None:
            X1, X2, Z = model.surface
            cm = RGBAColorMapper(Z.min(), Z.max(), standard_palettes[PALETTE])
            Y = cm.color(Z, alpha=IMAGE_ALPHA)
            self.train_fig.image_rgba(image=[Y], x=[0], y=[-50], dw=[100], dh=[100])
            self.test_fig.image_rgba(image=[Y], x=[0], y=[-50], dw=[100], dh=[100])

        sample_weight = model.sample_weight
        if sample_weight is None:
            sample_weight = np.ones(model.train.shape[0])

        sample_weight = np.sqrt(sample_weight) * DEFAULT_SIZE
        self.train_fig.circle(x=model.train[:, 0], y=model.train[:, 1],
                              color=color_code(model.train[:, 2]),
                              line_color="#7c7e71", size=sample_weight,
                              fill_alpha=FILL_ALPHA, line_alpha=LINE_ALPHA)
        self.test_fig.circle(x=model.test[:, 0], y=model.test[:, 1],
                             color=color_code(model.test[:, 2]),
                             line_color="#7c7e71", size=DEFAULT_SIZE,
                             fill_alpha=FILL_ALPHA, line_alpha=LINE_ALPHA)

        # yeah.. i dont like that either
        self.layout.children[1].children[1].children[0] = row(self.train_fig, self.test_fig)


class BokehTable(Table):

    def __init__(self, init_vals=None):
        if init_vals is None:
            init_vals = [[0.25, 0.25], [0.25, 0.25]]
        table_params = dict(start=0, end=1, step=.05, width=160)
        self.nw = Slider(title="NW", value=init_vals[0][0], **table_params)
        self.ne = Slider(title="NE", value=init_vals[0][1], **table_params)
        self.sw = Slider(title="SW", value=init_vals[1][0], **table_params)
        self.se = Slider(title="SE", value=init_vals[1][1], **table_params)

    def get_pd(self):
        return np.array([[self.nw.value, self.ne.value],
                         [self.sw.value, self.se.value]], dtype=np.float)

    def get_layout_element(self):
        return column(row(self.nw, self.ne), row(self.sw, self.se))


model = Model()
controller = Controller(model)
view = BokehView(controller)
model.add_observer(view)
view.update(model)

controller.set_train_pd(view.train_table)
controller.set_test_pd(view.test_table)

view.run()
