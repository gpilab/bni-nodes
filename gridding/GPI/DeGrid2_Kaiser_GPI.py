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
    """DeGridding module for Post-Cartesian Data - works with 2D data.
        First, data are rolloff corrected with the gridding kernel function.
        Second, zeroes are added around the image matrix according to the oversampling factor.
        Third, the data are inverse Fourer transformed and then gridded to the coordinate locations using a Kaiser-Bessel kernel.
        
    WIDGET:
        oversampling ratio: Oversampling and Kaiser-Bessel kernel function according to 
            Beatty, Philip J., Dwight G. Nishimura, and John M. Pauly. "Rapid gridding
            reconstruction with a minimal oversampling ratio." Medical Imaging, IEEE
            Transactions on 24.6 (2005): 799-808.

    INPUT:
        data: data in image domain
        coords: nD array sample locations (scaled between -0.5 and 0.5)
    
    OUTPUT:
        out: k-space resampled at coordinate locations
    """
    def initUI(self):
        # Widgets
        self.addWidget('DoubleSpinBox', 'oversampling ratio', val=1.375, decimals=3, singlestep=0.125, min=1, max=2, collapsed=True)
        

        # IO Ports
        self.addInPort('data', 'NPYarray', dtype=np.complex64, obligation=gpi.REQUIRED)
        self.addInPort('coords', 'NPYarray', dtype=[np.float64, np.float32], obligation=gpi.REQUIRED)
        self.addOutPort('out', 'NPYarray', dtype=np.complex64)

    def compute(self):

        import numpy as np
        import bni.gridding.grid_kaiser as dg

        crds = self.getData('coords').astype(np.float32, copy=False)
        gdata = self.getData('data').astype(np.complex64, copy=False)
        
        oversampling_ratio = self.getVal('oversampling ratio')
        mtx_original = gdata.shape[-1]
        mtx = np.int(mtx_original * oversampling_ratio)
        if mtx%2:
            mtx+=1
        if oversampling_ratio > 1:
            mtx_min = np.int((mtx-mtx_original)/2)
            mtx_max = mtx_min + mtx_original
        else:
            mtx_min = 0
            mtx_max = mtx
        
        # assume the last dims (i.e. each image) must be degridded independently
        gdata_iter, iter_shape = self.pinch(gdata, stop=-2)
        if iter_shape == []:
            iter_shape = [1]

        # construct an output array w/ slice dims
        out_shape = iter_shape + list(crds.shape)[:-1]
        out = np.zeros(out_shape, dtype=gdata.dtype)
        out_iter,_ = self.pinch(out, stop=-2)
        
        # pre-calculate Kaiser-Bessel kernel
        kernel_table_size = 800
        kernel = self.kaiserbessel_kernel( kernel_table_size, oversampling_ratio)
        
        # pre-calculate the rolloff for the spatial domain
        roll = self.rolloff2(mtx, kernel)

        # degrid all slices
        for i in range(np.prod(iter_shape)):
            oversampled_kspace = roll[mtx_min:mtx_max,mtx_min:mtx_max]*gdata_iter[i]
            oversampled_kspace = self.fft2(oversampled_kspace, dir=1, out_shape=[mtx, mtx])
            out_iter[i] = dg.degrid(crds, oversampled_kspace, kernel)

        # reset array shapes and output
        self.setData('out', out.squeeze())

        return(0)

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

    def rolloff2(self, mtx_xy, kernel, clamp_min_percent=10):
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
        out = np.abs(self.fft2(gd.grid(coords, data, weights, kernel, outdim, dx, dy)))

        # clamp the lowest values to a percentage of the max
        clamp = out.max() * clamp_min_percent/100.0
        out[out < clamp] = clamp

        # invert
        return 1.0/out

    def kaiserbessel_kernel(self, kernel_table_size, oversampling_ratio):
        #   Generate a Kaiser-Bessel kernel function
        #   OUTPUT: 1D kernel table for radius squared
    
        import bni.gridding.grid_kaiser as dg
        kernel_dim = np.array([kernel_table_size],dtype=np.int64)
        return dg.kaiserbessel_kernel(kernel_dim, np.float64(oversampling_ratio))


