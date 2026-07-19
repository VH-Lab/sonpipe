function channels = channels(filename, header)
% SONPIPE.CHANNELS - List channels in a CED SMR/SMRX file (NDR-style struct)
%
%   CHANNELS = sonpipe.channels(FILENAME)
%   CHANNELS = sonpipe.channels(FILENAME, HEADER)
%
%   Returns a struct array describing every recorded (non-Off) channel, in the
%   style of ndr.reader.ced_smr/getchannelsepoch. If HEADER is omitted it is
%   read from the file.
%
%   Each element has fields:
%     name          - NDR-style channel name (e.g. 'ai1' for analog_in ch 1)
%     type          - NDR channel type ('analog_in','event','mark','text')
%     number        - Spike2 channel number (1-based)
%     kind          - CED data-type code
%     time_channel  - the channel number (used as its time reference)
%
%   See also sonpipe.read_SOMSMR_header

	arguments
		filename {mustBeTextScalar}
		header = []            % [] or a header struct; read from FILENAME if omitted
	end

	if isempty(header)
		header = sonpipe.read_SOMSMR_header(filename);
	end

	channels = struct('name', {}, 'type', {}, 'number', {}, ...
		'kind', {}, 'time_channel', {});

	for k = 1:numel(header.channelinfo)
		c = header.channelinfo(k);
		entry.name = [prefix(c.ndr_type) int2str(c.number)];
		entry.type = c.ndr_type;
		entry.number = c.number;
		entry.kind = c.kind;
		entry.time_channel = c.number;
		channels(end+1) = entry; %#ok<AGROW>
	end
end

function p = prefix(ndrtype)
% Short NDR name prefix per channel type (mirrors ndr.reader.base.mfdaq_prefix).
	switch ndrtype
		case 'analog_in'
			p = 'ai';
		case 'event'
			p = 'e';
		case 'mark'
			p = 'mk';
		case 'text'
			p = 'text';
		otherwise
			p = 'ch';
	end
end
