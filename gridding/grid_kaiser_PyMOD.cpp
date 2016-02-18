/* Copyright (c) 2014, Dignity Health
 * All rights reserved.
 * 
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 * 
 * 1. Redistributions of source code must retain the above copyright notice, this
 * list of conditions and the following disclaimer.
 * 
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 * this list of conditions and the following disclaimer in the documentation
 * and/or other materials provided with the distribution.
 * 
 * 3. Neither the name of the copyright holder nor the names of its contributors
 * may be used to endorse or promote products derived from this software without
 * specific prior written permission.
 * 
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 * WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 * CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 * OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 *
 * Author: Nick Zwart
 * Date: 2013sep19
 * A python interface for the grid code.
 */

#include "PyFI/PyFI.h"
using namespace PyFI;
using namespace PyFI::FFTW;

#include <iostream>
using namespace std;

#include "bni/gridding/gridding.cpp"

PYFI_FUNC(grid)
{
    PYFI_START(); /* This must be the first line */

    /* input */
    PYFI_POSARG(Array<float>, crds);
    PYFI_POSARG(Array<complex<float> >, data);
    PYFI_POSARG(Array<float>, weights);
    PYFI_POSARG(Array<int64_t>, outdim);
    PYFI_POSARG(double, dx);
    PYFI_POSARG(double, dy);

    PYFI_SETOUTPUT_ALLOC_DIMS(Array<complex<float> >, outdata, outdim->size(), outdim->as_ULONG());

    _grid2(*data, *crds, *weights, *outdata, (float)*dx, (float)*dy);

    PYFI_END(); /* This must be the last line */
} /* grid */

PYFI_FUNC(rolloff)
{
    PYFI_START(); /* This must be the first line */

    /* input */
    PYFI_POSARG(Array<complex<float> >, data);
    PYFI_POSARG(Array<int64_t>, outdim);
    PYFI_POSARG(long, isofov);

    PYFI_SETOUTPUT_ALLOC_DIMS(Array<complex<float> >, outdata, outdim->size(), outdim->as_ULONG());

    _rolloff2(*data, *outdata, (int32_t) *isofov);

    PYFI_END(); /* This must be the last line */
} /* rolloff */

PYFI_FUNC(degrid)
{
    PYFI_START(); /* This must be the first line */

    /* input */
    PYFI_POSARG(Array<float>, crds);
    PYFI_POSARG(Array<complex<float> >, data);

    std::vector<uint64_t> outdim = crds->dimensions_vector();
    outdim.erase(outdim.begin());

    PYFI_SETOUTPUT_ALLOC(Array<complex<float> >, outdata, outdim);

    _degrid2(*data, *crds, *outdata);

    PYFI_END(); /* This must be the last line */
} /* grid */

PYFI_LIST_START_
    PYFI_DESC(grid, "Convolve points to a Cartesian grid.")
    PYFI_DESC(degrid, "Convolve points from a Cartesian grid to non-Cartesian coordinates.")
    PYFI_DESC(rolloff, "Rolloff Correction for the standard gridding calculation")
PYFI_LIST_END_
