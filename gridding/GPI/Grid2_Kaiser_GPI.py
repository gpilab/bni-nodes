# Copyright (c) 2014, Dignity Health
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# 1. Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
# 
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# 
# 3. Neither the name of the copyright holder nor the names of its contributors
# may be used to endorse or promote products derived from this software without
# specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Author: Nick Zwart
# Date: 2015nov25

import gpi
import numpy as np

class ExternalNode(gpi.NodeAPI):
    """Gridding module for Post-Cartesian Data - works with 2D data.
    """
    def initUI(self):
        # Widgets
        self.addWidget('SpinBox','mtx size (n x n)', min=5, val=240)
        self.addWidget('Slider','dims per set', min=1, val=2)

        # IO Ports
        self.addInPort('data', 'NPYarray', dtype=np.complex64, obligation=gpi.REQUIRED)
        self.addInPort('coords', 'NPYarray', dtype=np.float32, obligation=gpi.REQUIRED)
        self.addInPort('weights', 'NPYarray', dtype=np.float32, obligation=gpi.REQUIRED)
        self.addOutPort('out', 'NPYarray', dtype=np.complex64)
        self.addOutPort('deapodization', 'NPYarray')

    def validate(self):

        # adjust dims per set
        data = self.getData('data')
        crds = self.getData('coords')
        self.setAttr('dims per set', max=data.ndim)

        # Force the dims per set to be an dimension in excess of the coords
        # dimensions. This assumes the coords don't change between sets.
        self.setAttr('dims per set', quietval=crds.ndim-1)

        # Check for rolloff calc
        #   * Re-calc only if the dimensions changed
        d = self.getData('deapodization')
        dimensionsxy = self.getVal('mtx size (n x n)')
        if d is None:
            self.setData('deapodization', self.rolloff2(dimensionsxy))
        else:
            if list(d.shape) != [dimensionsxy, dimensionsxy]:
                self.setData('deapodization', self.rolloff2(dimensionsxy))

        return 0

    def compute(self):

        import numpy as np
        import bni.gridding.grid_kaiser as gd

        crds = self.getData('coords')
        data = self.getData('data')
        weights = self.getData('weights')
        dimensionsxy = self.getVal('mtx size (n x n)')
        dimsperset = self.getVal('dims per set')

        # construct an output array w/ slice dims
        data_iter, iter_shape = self.pinch(data, stop=-dimsperset)

        # assume the last dims (i.e. each image) must be gridded independently
        # shape = [..., n, n], where 'n' is the image dimensions
        image_shape = [dimensionsxy, dimensionsxy]
        out_shape = iter_shape + image_shape
        out = np.zeros(out_shape, dtype=data.dtype)
        out_iter,_ = self.pinch(out, stop=-dimsperset)

        # tell the grid routine what shape to produce
        outdim = np.array(image_shape, dtype=np.int64) 

        # grid all slices
        dx = dy = 0.
        for i in range(np.prod(iter_shape)):
            out_iter[i] = gd.grid(crds, data_iter[i], weights, outdim, dx, dy)

        self.setData('out', out)

        return 0 

    def fft2(self, data, dir=0, zp=1, out_shape=[], tx_ON=True):
        # data: np.complex64
        # dir: int (0 or 1)
        # zp: float (>1)

        # simplify the fftw wrapper
        import numpy as np
        import core.math.fft as corefft

        # generate output dim size array
        # fortran dimension ordering
        outdims = list(data.shape)
        if len(out_shape):
            outdims = out_shape
        else:
            for i in range(len(outdims)):
                outdims[i] = int(outdims[i]*zp)
        outdims.reverse()
        outdims = np.array(outdims, dtype=np.int64)

        # load fft arguments
        kwargs = {}
        kwargs['dir'] = dir

        # transform or just zeropad
        if tx_ON:
            kwargs['dim1'] = 1
            kwargs['dim2'] = 1
        else:
            kwargs['dim1'] = 0
            kwargs['dim2'] = 0

        return corefft.fftw(data, outdims, **kwargs)

    def rolloff2(self, mtx_xy, clamp_min_percent=5):
        # mtx_xy: int
        import numpy as np
        import bni.gridding.grid_kaiser as gd

        # grid one point at k_0
        dx = dy = 0.0
        coords = np.array([0,0], dtype='float32')
        data = np.array([1.0], dtype='complex64')
        weights = np.array([1.0], dtype='float32')
        outdim = np.array([mtx_xy, mtx_xy],dtype=np.int64)

        # grid -> fft -> |x|
        out = np.abs(self.fft2(gd.grid(coords,data,weights,outdim,dx,dy)))

        # clamp the lowest values to a percentage of the max
        clamp = out.max() * clamp_min_percent/100.0
        out[out < clamp] = clamp

        # invert
        return 1.0/out

    def execType(self):
        return gpi.GPI_PROCESS

    def pinch(self, a, start=0, stop=-1):
        '''Combine multiple adjacent dimensions into one by taking the product
        of dimension lengths.  The output array is a view of the input array.
        INPUT:
            a: input array
            start: first dimension to pinch
            stop: last dimension to pinch
        OUTPUT:
            out: a view of the input array with pinched dimensions
            iter_shape: a list of dimensions that will be iterated on
        '''
        import numpy as np
        out = a.view()
        s = list(a.shape)
        iter_shape = s[start:stop]
        out_shape = s[:start] + [np.prod(iter_shape)] + s[stop:]
        out.shape = out_shape
        return out, iter_shape