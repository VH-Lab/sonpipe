% SONPIPE  MATLAB client for the sonpipe command-line bridge.
%
%   The +sonpipe package reads Cambridge Electronic Design (CED) Spike2 data
%   files by calling the standalone "sonpipe" command-line tool, which in turn
%   uses CED's proprietary sonpy library. Python runs in its own isolated
%   process; nothing is loaded into the MATLAB interpreter, so there are no
%   version locks or interpreter crashes.
%
%   Both file formats are supported transparently, because sonpy reads both:
%     * 32-bit .smr  (legacy Spike2 "son32" files)
%     * 64-bit .smrx ("son64" files)
%
%   These functions are drop-in analogues of the ndr.format.ced.* functions in
%   NDR-matlab, so code written against those functions works with only a
%   change of package prefix (ndr.format.ced -> sonpipe).
%
%   Reading functions:
%     read_SOMSMR_header          - read file + channel header information
%     read_SOMSMR_sampleinterval  - sample interval / rate for one channel
%     read_SOMSMR_datafile        - read waveform, event or marker data
%
%   Helpers:
%     channels                    - list channels as an NDR-style struct array
%     channelinfo                 - look up one channel's header entry
%     executable                  - locate / set / query the sonpipe CLI command
%
%   Setup:
%     1. Install the CLI:   pip install sonpipe
%     2. Add this folder's PARENT (the one containing +sonpipe) to the MATLAB
%        path:              addpath('/path/to/sonpipe/matlab')
%     3. (optional) If "sonpipe" is not on the system PATH, point MATLAB at it:
%                           sonpipe.executable('/full/path/to/sonpipe')
%        or set the SONPIPE environment variable.
%
%   Example:
%     f = '/data/example.smrx';
%     h = sonpipe.read_SOMSMR_header(f);
%     sr = 1/sonpipe.read_SOMSMR_sampleinterval(f, h, 21);
%     [d,~,~,~,t] = sonpipe.read_SOMSMR_datafile(f, h, 21, 0, 100);
%     plot(t, d);
%
%   See also NDR (https://github.com/VH-Lab/NDR-matlab).
