#ifndef _LOLSPEAKLIB__LOLSPEAK__H_
#define _LOLSPEAKLIB__LOLSPEAK__H_

#include "translator.h"
#include <map>


namespace translate {

	/*
	 * @class LolTranslator
	 * @brief
	 * Lolspeak translator.
	 */
	class LolTranslator : public Translator
	{
	public:
		LolTranslator();
		virtual std::string getSentence(const std::string& sentence) const;
		virtual std::string getWord(const std::string& word) const;

		// new function added in 2.1.0
		void setExtremeLOL(bool b) { m_extreme=b; }

	protected:
		typedef std::map<std::string, std::string> word_map;
		word_map m_words;
		bool m_extreme;
	};

}

#endif
