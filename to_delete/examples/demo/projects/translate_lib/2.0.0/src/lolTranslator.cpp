#include "lolTranslator.h"

namespace translate {

LolTranslator::LolTranslator()
{
	m_words.insert(word_map::value_type("hello", "oh hai"));
	m_words.insert(word_map::value_type("have", "haz"));
	m_words.insert(word_map::value_type("cheeseburger", "cheezburger"));
}


std::string LolTranslator::getSentence(const std::string& sentence) const
{
	return Translator::getSentence(sentence);
}


std::string LolTranslator::getWord(const std::string& word) const
{
	word_map::const_iterator it = m_words.find(word);
	return (it == m_words.end())? word : it->second;
}

}
