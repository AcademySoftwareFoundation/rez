#include "ghettoTranslator.h"
#include <iostream>
#include <algorithm>

namespace translate {

GhettoTranslator::GhettoTranslator()
{
	m_words.insert(word_map::value_type("hello", "sup"));
	m_words.insert(word_map::value_type("friend", "dogg"));
	m_words.insert(word_map::value_type("it", "dis shizzle"));
	m_words.insert(word_map::value_type("going", "doin"));
}


std::string GhettoTranslator::getWord(const std::string& word) const
{
	word_map::const_iterator it = m_words.find(word);
	return (it == m_words.end())? word : it->second;
}

}
