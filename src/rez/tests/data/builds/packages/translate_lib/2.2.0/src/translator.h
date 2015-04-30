#ifndef _TRANSLATE__TRANSLATOR__H_
#define _TRANSLATE__TRANSLATOR__H_

#include <string>


namespace translate {

	/*
	 * @class Translator
	 * @brief
	 * Abstract base class for speech translation.
	 */
	class Translator
	{
	public:
		Translator(){}

		/*
		 * @brief getSentence
		 * Translate the given sentence into the target language.
		 */
		virtual std::string getSentence(const std::string& sentence) const;

		/*
		 * @brief getWord
		 * Translate the given word into the target language.
		 */
		virtual std::string getWord(const std::string& word) const = 0;
	};

}

#endif
