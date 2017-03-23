
hai: ${REZ_BUILD_SOURCE_PATH}/lib/main.cpp
	g++ -o hai ${REZ_BUILD_SOURCE_PATH}/lib/main.cpp

.PHONY: install
install: hai
	mkdir -p ${REZ_BUILD_INSTALL_PATH}/bin
	cp $< ${REZ_BUILD_INSTALL_PATH}/bin/hai
