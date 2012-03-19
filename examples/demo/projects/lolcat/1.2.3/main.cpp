#include <translate/lolTranslator.h>
#include <iostream>

using namespace translate;

#define STRINGIFY2(X) #X
#define STRINGIFY(X) STRINGIFY2(X)


int main(int argc, char** argv)
{
	LolTranslator trans;

#if TRANSLATE_MAJOR_VER >= 2
#if TRANSLATE_MINOR_VER >= 1
	trans.setExtremeLOL(true);
#endif
#endif

	std::string s = trans.getSentence("Can I have a cheeseburger soon?!");
	std::cout << s << std::endl;

	return 0;
}
