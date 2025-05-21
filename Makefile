# # # # # CREATE PCKs and SPK for NGC GALAXIES  # # # # #

### Source for PINPOINT executable, if one is not in shell's PATH
PINPOINT_URL = https://naif.jpl.nasa.gov/pub/naif/utilities/PC_Linux_64bit/pinpoint

### Separate dependencies for PCKs and SPK,
### - so PCKs are not remade if only SPK is missing
all:
	@make \
generators/NGC_625.tpc \
generators/NGC_660.tpc \
generators/NGC_891.tpc \
generators/NGC_1353.tpc \
generators/NGC_1406.tpc \
generators/NGC_1448.tpc | grep -v 'ing directory '

	@make spk/galaxies.bsp | grep -v 'ing directory '

### If any NGC PCK is missing, recreate everything
generators/NGC_%.tpc:

        # Cleanup SPK first, if present
	$(RM) spk/galaxies.bsp

        # Generate PCKs and SPK
	python generators/galaxy_pck_gen.py

### If SPK is missing, use PINPOINT SPICE utility
spk/galaxies.bsp:

        # Cleanup first, so wget does not create pinpoint.1
	@$(RM) generators/ngc.defs generators/pinpoint

        # Create definitions file; order galaxies by site ID
	@grep SITE9999..._CENTER generators/NGC_*.tpc \
	| sort -t: -k2 \
	| sed 's/:.*//' \
	| xargs cat > generators/ngc.defs

        # Use local PINPOINT if present, else get executable from NAIF
	@which pinpoint > /dev/null \
	&& pinpoint -def generators/ngc.defs -spk $@ \
	&& ( echo "Generated $@ using local PINPOINT executable" || true ) \
	|| ( wget -nv $(PINPOINT_URL) -P generators \
	   && chmod a+x generators/pinpoint \
	   && generators/pinpoint -def generators/ngc.defs -spk $@ \
	   && ( echo "Generated $@ using PINPOINT from NAIF website" \
	      || true \
	      ) \
	   )

        # Cleanup
	@$(RM) generators/ngc.defs generators/pinpoint
