# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# Convenience variables to add colour to the MESSAGE output provided by CMake.
# These variables make use of standard terminal escape sequences.  This only
# affects the output during the cmake configuration step, and not execution of
# Makefiles etc.
#
# The MESSAGE command is redefined here to ensure all CMake generated messages
# are colorized by default.
#
# This implementation is taken from the answer given by 'Fraser' in
# http://stackoverflow.com/questions/18968979/how-to-get-colorized-output-with-cmake

# segfault if this file is included more than once... :/
if(NOT _COLORIZE_INCLUDED)

    if(NOT WIN32)
      string(ASCII 27 Esc)
      set(ColourReset "${Esc}[m")
      set(ColourBold  "${Esc}[1m")

      set(ColorReset  "${Esc}[m")  # for the Americans
      set(ColorBold   "${Esc}[1m")

      set(Red         "${Esc}[31m")
      set(Green       "${Esc}[32m")
      set(Yellow      "${Esc}[33m")
      set(Blue        "${Esc}[34m")
      set(Magenta     "${Esc}[35m")
      set(Cyan        "${Esc}[36m")
      set(White       "${Esc}[37m")
      set(BoldRed     "${Esc}[1;31m")
      set(BoldGreen   "${Esc}[1;32m")
      set(BoldYellow  "${Esc}[1;33m")
      set(BoldBlue    "${Esc}[1;34m")
      set(BoldMagenta "${Esc}[1;35m")
      set(BoldCyan    "${Esc}[1;36m")
      set(BoldWhite   "${Esc}[1;37m")
    endif()

    function(message)
        list(LENGTH ARGV length)
        if (NOT length EQUAL 0)
            list(GET ARGV 0 MessageType)
            if(MessageType STREQUAL FATAL_ERROR OR MessageType STREQUAL SEND_ERROR)
                list(REMOVE_AT ARGV 0)
                _message(${MessageType} "${BoldRed}${ARGV}${ColourReset}")
            elseif(MessageType STREQUAL WARNING)
                list(REMOVE_AT ARGV 0)
                _message(${MessageType} "${BoldYellow}${ARGV}${ColourReset}")
            elseif(MessageType STREQUAL AUTHOR_WARNING)
                list(REMOVE_AT ARGV 0)
                _message(${MessageType} "${BoldCyan}${ARGV}${ColourReset}")
            elseif(MessageType STREQUAL STATUS)
                list(REMOVE_AT ARGV 0)
                _message(${MessageType} "${Green}${ARGV}${ColourReset}")
            else()
                _message("${ARGV}")
            endif()
        endif()
    endfunction()

    set(_COLORIZE_INCLUDED 1)

endif()
