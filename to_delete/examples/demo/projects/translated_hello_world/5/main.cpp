#include <translate/lolTranslator.h>
#include <iostream>

using namespace translate;


int main(int argc, char** argv)
{
	LolTranslator trans;
	std::string s = trans.getSentence("hello world!");
	std::cout << s << std::endl;

	return 0;
}
