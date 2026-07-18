classdef TestCase < matlab.unittest.TestCase
% sonpipe.unittest.TestCase - Base fixture for the +sonpipe MATLAB unit tests
%
%   Points sonpipe.executable at a fake sonpipe CLI (fakecli.py) that runs the
%   real sonpipe Python code against a synthetic in-memory file, so the MATLAB
%   wrappers can be tested end-to-end without CED's sonpy binaries.
%
%   Tests are skipped (filtered) if a working Python 3 with numpy is not found.

	properties
		File   % path to a temporary (synthetic) data file
	end

	methods (TestClassSetup)
		function configureFakeCli(tc)
			here = fileparts(mfilename('fullpath'));
			fakecli = fullfile(here, 'fakecli.py');

			py = sonpipe.unittest.TestCase.findPython();
			tc.assumeFalse(isempty(py), ...
				'Python 3 not found on PATH; skipping +sonpipe MATLAB tests.');

			cmd = sprintf('%s "%s"', py, fakecli);
			[status, ~] = sonpipe.runcmd([cmd ' --version']);
			tc.assumeEqual(status, 0, ...
				['The sonpipe fake CLI could not run (is numpy installed for ' ...
				 'this Python?); skipping +sonpipe MATLAB tests.']);

			sonpipe.executable(cmd);

			tc.File = [tempname() '.smrx'];
			fid = fopen(tc.File, 'w');
			fwrite(fid, 0, 'uint8');
			fclose(fid);
		end
	end

	methods (TestClassTeardown)
		function cleanupFile(tc)
			if ~isempty(tc.File) && exist(tc.File, 'file')
				delete(tc.File);
			end
		end
	end

	methods (Static)
		function py = findPython()
			py = '';
			candidates = {'python3', 'python'};
			for i = 1:numel(candidates)
				[status, ~] = sonpipe.runcmd([candidates{i} ' --version']);
				if status == 0
					py = candidates{i};
					return;
				end
			end
		end
	end
end
