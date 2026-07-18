function results = run_all(varargin)
% SONPIPE.UNITTEST.RUN_ALL - Run every +sonpipe MATLAB unit test
%
%   RESULTS = sonpipe.unittest.run_all()
%
%   Adds the repository's 'matlab' (source) and 'test' folders to the MATLAB
%   path and runs all tests in the sonpipe.unittest namespace. Any extra
%   arguments are forwarded to RUNTESTS (e.g. 'OutputDetail','Detailed').
%
%   Requires a working Python 3 with numpy so the fake sonpipe CLI can run;
%   individual tests are skipped if it is unavailable.
%
%   Example:
%     results = sonpipe.unittest.run_all();
%     assert(all(~[results.Failed]));

	here = fileparts(mfilename('fullpath'));
	repo = fileparts(fileparts(fileparts(here)));  % .../repo

	addpath(fullfile(repo, 'matlab'));
	addpath(fullfile(repo, 'test'));

	results = runtests('sonpipe.unittest', varargin{:});

	if nargout == 0
		disp(results);
		clear results;
	end
end
