PINPOINT_URL = https://naif.jpl.nasa.gov/pub/naif/utilities/PC_Linux_64bit/pinpoint

all:
	@make -s \
generators/NGC_1353.tpc \
generators/NGC_1406.tpc \
generators/NGC_1448.tpc \
generators/NGC_625.tpc \
generators/NGC_660.tpc \
generators/NGC_891.tpc

	@make spk/galaxies.bsp

generators/NGC_1353.tpc \
generators/NGC_1406.tpc \
generators/NGC_1448.tpc \
generators/NGC_625.tpc \
generators/NGC_660.tpc \
generators/NGC_891.tpc \
:
	$(RM) spk/galaxies.bsp
	python generators/galaxy_pck_gen.py

spk/galaxies.bsp:

	@$(RM) generators/ngc.defs generators/pinpoint

	@grep SITE9999..._CENTER generators/NGC_*.tpc \
	| sort -t: -k2 \
	| sed 's/:.*//' \
	| xargs cat > generators/ngc.defs

	@which pinpointx > /dev/null \
	&& pinpoint -def generators/ngc.defs -spk $@ \
	|| ( wget -nv $(PINPOINT_URL) -P generators \
	   && chmod a+x generators/pinpoint \
	   && generators/pinpoint -def generators/ngc.defs -spk $@ \
	   && ( echo "Generated $@ using pinpoint from NAIF website" \
	      || true \
	      ) \
	   )

	$(RM) generators/ngc.defs generators/pinpoint
