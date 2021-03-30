#include "translator.h"
#include <sstream>

namespace translate {

std::string Translator::getSentence(const std::string& sentence) const
{
	std::istringstream iss(sentence);
	std::ostringstream oss;

	unsigned int nwords = 0;
	while(iss.good())
	{
		std::string s;
		iss >> s;
		if(nwords > 0)
			oss << " ";
		oss << getWord(s);
		++nwords;
	}

	return oss.str();
}

}
