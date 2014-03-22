#include "ghetto_greet.h"
#include <translate/ghettoTranslator.h>

namespace supworld {

std::string ghetto_greet()
{
	translate::GhettoTranslator trans;
	std::string s("hello friend - how is it going today?");
	return trans.getSentence(s);
}

}
