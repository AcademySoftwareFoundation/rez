#include "spanish_greet.h"
#include <translate/spanishTranslator.h>

namespace supworld {

std::string spanish_greet()
{
	translate::SpanishTranslator trans;
	std::string s("hello friend");
	return trans.getSentence(s);
}

}
