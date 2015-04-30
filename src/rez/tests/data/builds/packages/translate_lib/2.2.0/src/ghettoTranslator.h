#ifndef _LOLSPEAKLIB__GHETTOSPEAK__H_
#define _LOLSPEAKLIB__GHETTOSPEAK__H_

#include "translator.h"
#include <map>


namespace translate {

	/*
	 * @class GhettoTranslator
	 * @brief
	 * Ghetto translator.
	 */
	class GhettoTranslator : public Translator
	{
	public:
		GhettoTranslator();
		virtual std::string getWord(const std::string& word) const;

	protected:
		typedef std::map<std::string, std::string> word_map;
		word_map m_words;
	};

}

#endif
