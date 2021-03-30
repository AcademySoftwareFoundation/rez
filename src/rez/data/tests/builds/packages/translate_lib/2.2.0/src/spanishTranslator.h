#ifndef _LOLSPEAKLIB__SPANISHSPEAK__H_
#define _LOLSPEAKLIB__SPANISHSPEAK__H_

#include "translator.h"
#include <map>


namespace translate {

	class SpanishTranslator : public Translator
	{
	public:
		SpanishTranslator();
		virtual std::string getWord(const std::string& word) const;

	protected:
		typedef std::map<std::string, std::string> word_map;
		word_map m_words;
	};

}

#endif
