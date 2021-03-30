#include "spanishTranslator.h"
#include <iostream>
#include <algorithm>

namespace translate {

SpanishTranslator::SpanishTranslator()
{
	m_words.insert(word_map::value_type("hello", "hola"));
	m_words.insert(word_map::value_type("friend", "amigo"));
}


std::string SpanishTranslator::getWord(const std::string& word) const
{
	word_map::const_iterator it = m_words.find(word);
	return (it == m_words.end())? word : it->second;
}

}
